import random

import structlog

logger = structlog.get_logger()

MUTABLE_FIELDS = ["copy_text", "script", "image_prompt", "target_audience"]


class CrossoverService:
    """
    Combines traits from two winning campaigns using uniform crossover.
    For each field, randomly pick from parent A or B.
    """

    def crossover(
        self,
        parent_a: dict,
        parent_b: dict,
        crossover_rate: float,
    ) -> dict:
        """
        Uniform crossover: for each mutable field, pick from parent_b
        with probability crossover_rate, else from parent_a.
        """
        offspring = dict(parent_a)

        for field in MUTABLE_FIELDS:
            if field not in parent_b:
                continue

            if random.random() < crossover_rate:
                if field == "target_audience":
                    offspring[field] = self._crossover_audience(
                        parent_a.get(field, {}),
                        parent_b.get(field, {}),
                        crossover_rate,
                    )
                else:
                    offspring[field] = parent_b[field]

        logger.debug("crossover_complete")
        return offspring

    def _crossover_audience(
        self,
        audience_a: dict,
        audience_b: dict,
        crossover_rate: float,
    ) -> dict:
        """Field-level crossover for target_audience dict."""
        result = dict(audience_a)

        # Age range — pick pair from one parent
        if random.random() < crossover_rate:
            result["age_min"] = audience_b.get("age_min", result.get("age_min"))
            result["age_max"] = audience_b.get("age_max", result.get("age_max"))

        # Genders — pick from one parent
        if random.random() < crossover_rate:
            result["genders"] = audience_b.get("genders", result.get("genders", []))

        # Interests — merge and deduplicate, randomly drop some
        interests_a = set(audience_a.get("interests", []))
        interests_b = set(audience_b.get("interests", []))
        merged = list(interests_a | interests_b)
        # Randomly keep ~75% of merged interests
        kept = [i for i in merged if random.random() < 0.75]
        result["interests"] = kept if kept else merged[:1]

        # Locations — pick from one parent
        if random.random() < crossover_rate:
            result["locations"] = audience_b.get(
                "locations", result.get("locations", [])
            )

        return result
