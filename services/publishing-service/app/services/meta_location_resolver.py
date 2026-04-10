"""
Resolves human-readable location names to Meta Ads geo_location targeting specs.

Uses Meta's Targeting Search API via the facebook-business SDK (TargetingSearch).
"""

import unicodedata

import structlog
from facebook_business.adobjects.targetingsearch import TargetingSearch
from facebook_business.api import FacebookAdsApi
from facebook_business.exceptions import FacebookRequestError

logger = structlog.get_logger()


def _normalise(s: str) -> str:
    """Strip accents and lowercase for fuzzy region comparison."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()

# Module-level cache: city lookups don't change, safe to share across calls
_city_cache: dict[str, dict | None] = {}


class MetaLocationResolver:
    """Resolves location names to Meta geo_location targeting format.

    Usage:
        resolver = MetaLocationResolver(api_instance)
        result = resolver.resolve(locations_from_proposal)
        # result.geo_locations: {"cities": [{"key": "2720166"}]} or {"countries": ["CO"]}
        # result.resolved_for_storage: {"cities": [{"key": "2720166", "name": "Cali", "region": "..."}]}
    """

    def __init__(self, api: FacebookAdsApi):
        self.api = api

    def resolve(self, locations: list) -> tuple[dict, dict]:
        """Takes the locations array from a proposal's target_audience and
        returns a tuple of (geo_locations_for_meta, resolved_for_storage).

        geo_locations_for_meta: {"cities": [{"key": "2720166"}]} or {"countries": ["CO"]}
        resolved_for_storage:  {"cities": [{"key": "2720166", "name": "Cali", "region": "..."}]}

        Handles three input formats:
        1. NEW city format:   [{"type": "city", "name": "Cali", ...}]
        2. NEW country format: [{"type": "country", "country_code": "CO"}]
        3. OLD string format:  ["CO"]  (backward compat)
        """
        if not locations:
            logger.warning("no_locations_provided", fallback="CO")
            fallback = {"countries": ["CO"]}
            return fallback, fallback

        meta_cities: list[dict] = []       # {"key": "..."} for Meta API
        storage_cities: list[dict] = []    # {"key": "...", "name": "...", "region": "..."} for DB
        countries: list[str] = []

        for loc in locations:
            if isinstance(loc, str):
                # Old format: bare country code
                countries.append(loc)
            elif isinstance(loc, dict):
                loc_type = loc.get("type", "country")
                if loc_type == "city":
                    name = loc.get("name", "")
                    region = loc.get("region")
                    country_code = loc.get("country_code", "CO")
                    resolved = self._resolve_city(
                        name=name,
                        country_code=country_code,
                        region=region,
                    )
                    if resolved:
                        meta_cities.append({"key": resolved["key"]})
                        storage_cities.append({
                            "key": resolved["key"],
                            "name": name,
                            "region": region or "",
                        })
                elif loc_type == "country":
                    countries.append(loc.get("country_code", "CO"))

        geo_locations = self._build_geo_locations(meta_cities, countries)

        # Build storage version
        if storage_cities:
            resolved_for_storage = {"cities": storage_cities}
        elif countries:
            resolved_for_storage = {"countries": countries}
        else:
            resolved_for_storage = {"countries": ["CO"]}

        return geo_locations, resolved_for_storage

    def _resolve_city(self, name: str, country_code: str, region: str | None = None) -> dict | None:
        """Calls Meta Targeting Search API to find the city key.

        Returns {"key": "2720166"} or None.
        """
        cache_key = f"{name.lower()}:{country_code.lower()}:{(region or '').lower()}"
        if cache_key in _city_cache:
            return _city_cache[cache_key]

        try:
            results = TargetingSearch.search(
                params={
                    "q": name,
                    "type": TargetingSearch.TargetingSearchTypes.geolocation,
                    "location_types": ["city"],
                    "country_code": country_code,
                },
                api=self.api,
            )

            if not results:
                logger.warning("meta_city_not_found", city=name, country=country_code)
                _city_cache[cache_key] = None
                return None

            # Pick the best match — prioritise region match to avoid
            # same-name cities (e.g. Cali, Valle del Cauca vs Cali, Córdoba)
            best = None
            if len(results) == 1:
                best = results[0]
            else:
                name_lower = name.lower()
                name_matches: list = []
                for r in results:
                    r_name = (r.get("name") or "").lower()
                    if r_name == name_lower:
                        name_matches.append(r)

                if not name_matches:
                    # No exact name match — fall back to first result
                    best = results[0]
                elif len(name_matches) == 1:
                    best = name_matches[0]
                elif region:
                    # Multiple cities with the same name — use region to disambiguate.
                    # Pass 1: exact normalized match (accent-insensitive).
                    # Pass 2: substring fallback (handles "Valle del Cauca" vs
                    #          "Valle del Cauca Department").
                    region_norm = _normalise(region)

                    # Pass 1 — exact
                    for r in name_matches:
                        if _normalise(r.get("region") or "") == region_norm:
                            best = r
                            break

                    # Pass 2 — substring (only if exact failed)
                    if best is None:
                        for r in name_matches:
                            r_region_norm = _normalise(r.get("region") or "")
                            if region_norm in r_region_norm or r_region_norm in region_norm:
                                best = r
                                break

                    if best is None:
                        # Region didn't match any — take first name match
                        best = name_matches[0]
                        logger.warning(
                            "meta_city_region_mismatch",
                            city=name,
                            expected_region=region,
                            picked_region=best.get("region"),
                            all_regions=[r.get("region") for r in name_matches],
                        )
                else:
                    best = name_matches[0]

            resolved = {"key": str(best["key"])}
            _city_cache[cache_key] = resolved
            logger.info(
                "meta_city_resolved",
                city=name,
                key=best["key"],
                meta_name=best.get("name"),
                meta_region=best.get("region"),
            )
            return resolved

        except FacebookRequestError as exc:
            error_code = exc.api_error_code()
            # Re-raise fatal errors (expired token, rate limit) — don't silently degrade
            if error_code in (190, 17, 613):
                raise
            logger.warning("meta_city_search_failed", city=name, error=str(exc))
            _city_cache[cache_key] = None
            return None

    def _build_geo_locations(self, resolved_cities: list[dict], countries: list[str]) -> dict:
        """Builds the final geo_locations dict.

        If any cities were resolved, use cities only (Meta rejects mixing).
        """
        if resolved_cities:
            return {"cities": resolved_cities}
        if countries:
            return {"countries": countries}
        # Fallback
        logger.warning("no_locations_resolved", fallback="CO")
        return {"countries": ["CO"]}
