from bluesky_widgets.models.search import Search

headings = (
    "Unique ID",
    "Scan ID",
    "Plan Name",
    "Start Time",
    "Duration",
    "Exit Status",
)


def extract_results_row_from_run(run):
    """
    Given a BlueskyRun, format a row for the table of search results.
    """
    from datetime import datetime

    metadata = run.describe()["metadata"]
    start = metadata["start"]
    stop = metadata["stop"]
    start_time = datetime.fromtimestamp(start["time"])
    if stop is None:
        str_duration = "-"
    else:
        duration = datetime.fromtimestamp(stop["time"]) - start_time
        str_duration = str(duration)
        str_duration = str_duration[: str_duration.index(".")]
    return (
        start["uid"][:8],
        start.get("scan_id", "-"),
        start.get("plan_name", "-"),
        start_time.strftime("%Y-%m-%d %H:%M:%S"),
        str_duration,
        "-" if stop is None else stop["exit_status"],
    )


columns = (headings, extract_results_row_from_run)


class AddSearchMixin:
    """Provide an add_search method that makes a Search.

    This purpose is to provide a top-level method that has a default column layout.
    """

    def add_search(self, catalog, columns=extract_results_row_from_run):
        """
        Add a new Search form.
        """
        search = Search(catalog, columns=(headings, extract_results_row_from_run))
        self.searches.append(search)

    @property
    def active_search(self):
        """
        Convenience for accessing the currently-active Search form.
        """
        return self.searches.active
