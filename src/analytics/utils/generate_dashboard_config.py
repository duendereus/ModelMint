import pandas as pd


def generate_dashboard_config(df: pd.DataFrame) -> dict:
    """
    Automatically generates a dashboard config JSON structure from a given DataFrame.

    Returns:
        dict: Dashboard configuration with filters, charts and column metadata.
    """
    config = {
        "filters": [],
        "charts": [],
        "columns": df.columns.tolist(),
    }

    # Detect filters: categorical variables with low cardinality
    for col in df.columns:
        unique_vals = df[col].nunique()
        if (df[col].dtype == "object" and unique_vals <= 30) or df[
            col
        ].dtype.name == "category":
            config["filters"].append(col)

    # Detect numeric variables for Y axis
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()

    # Detect temporal or ordinal columns for X axis
    candidate_x = []
    for col in df.columns:
        if "date" in col.lower() or "month" in col.lower() or "week" in col.lower():
            candidate_x.append(col)
        elif df[col].dtype == "object" and df[col].nunique() <= 30:
            candidate_x.append(col)

    # Default chart suggestions
    for y_col in numeric_cols:
        for x_col in candidate_x:
            if x_col != y_col:
                chart = {
                    "type": "bar",
                    "title": f"{y_col.title()} by {x_col.title()}",
                    "x": x_col,
                    "y": y_col,
                    "group_by": config["filters"][0] if config["filters"] else None,
                    "aggregation": "sum",
                }
                config["charts"].append(chart)

    return config


def validate_dashboard_config(config: dict) -> bool:
    """
    Validates that all chart fields refer to existing columns.
    Returns True if valid, raises ValueError if not.
    """
    columns = set(config.get("columns", []))

    for chart in config.get("charts", []):
        for key in ("x", "y", "group_by"):
            val = chart.get(key)
            if val and val not in columns:
                raise ValueError(
                    f"Invalid field '{val}' in chart config. Not found in columns."
                )

        if chart.get("aggregation") not in ("sum", "avg", "count"):
            raise ValueError(f"Invalid aggregation: {chart.get('aggregation')}")

        if chart.get("type") not in ("bar", "line", "area", "scatter"):
            raise ValueError(f"Invalid chart type: {chart.get('type')}")

    return True


def pretty_title(y_col, x_col, group_by=None):
    """
    Retorna un título legible como:
    'Asistencia Total por Fecha (por Studio)'
    """

    def beautify(label):
        return label.replace("_", " ").capitalize()

    title = f"{beautify(y_col)} por {beautify(x_col)}"
    if group_by and group_by not in (x_col, y_col):
        title += f" (por {beautify(group_by)})"
    return title
