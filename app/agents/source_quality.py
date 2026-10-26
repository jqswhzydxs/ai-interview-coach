from typing import Any


EXECUTION_MODE_TO_QUALITY = {
    "real": "trusted",
    "mock": "synthetic",
    "fallback": "degraded",
    "user": "user_provided",
}


def source_record(
    execution_mode: str,
    *,
    agent_run_id: object | None = None,
) -> dict:
    normalized_mode = str(execution_mode or "unknown").lower()
    record = {
        "execution_mode": normalized_mode,
        "source_quality": EXECUTION_MODE_TO_QUALITY.get(normalized_mode, "unknown"),
    }
    if agent_run_id is not None:
        record["agent_run_id"] = str(agent_run_id)
    return record


def source_record_from_run(run: Any | None) -> dict:
    if run is None:
        return source_record("unknown")
    return source_record(
        getattr(run, "execution_mode", "unknown"),
        agent_run_id=getattr(run, "id", None),
    )


def source_context_from_metadata(**sources: Any) -> dict[str, dict]:
    context: dict[str, dict] = {}
    for name, metadata in sources.items():
        if metadata is None:
            context[name] = source_record("unknown")
        else:
            context[name] = source_record(
                getattr(metadata, "execution_mode", "unknown"),
            )
    return context


def fallback_source_names(input_data_or_context: dict | None) -> list[str]:
    context = _source_context(input_data_or_context)
    return sorted(
        name
        for name, item in context.items()
        if isinstance(item, dict)
        and (
            str(item.get("execution_mode", "")).lower() == "fallback"
            or str(item.get("source_quality", "")).lower() == "degraded"
        )
    )


def aggregate_source_quality(input_data_or_context: dict | None) -> str:
    context = _source_context(input_data_or_context)
    qualities = {
        str(item.get("source_quality", "unknown")).lower()
        for item in context.values()
        if isinstance(item, dict)
    }
    if not qualities or qualities == {"unknown"}:
        return "unknown"
    if "degraded" in qualities:
        return "degraded"
    if "synthetic" in qualities:
        return "synthetic" if qualities <= {"synthetic", "unknown"} else "mixed"
    if qualities <= {"trusted", "user_provided", "unknown"}:
        if qualities == {"trusted"}:
            return "trusted"
        if qualities == {"user_provided"}:
            return "user_provided"
        return "mixed"
    return "mixed"


def _source_context(input_data_or_context: dict | None) -> dict:
    if not isinstance(input_data_or_context, dict):
        return {}
    nested = input_data_or_context.get("source_context")
    if isinstance(nested, dict):
        return nested
    return input_data_or_context
