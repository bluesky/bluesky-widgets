import contextlib

from ipywidgets.widgets import (
    Text,
    VBox,
    RadioButtons,
    HBox,
    Label,
    Button,
    Layout,
    GridBox,
)
from traitlets import All
from ipydatetime import DatetimePicker
from datetime import datetime, timedelta
from bluesky_widgets.models.search import LOCAL_TIMEZONE


class JupyterSearchInput(HBox):
    def __init__(self, model, *args, **kwargs):
        self.model = model
        self._fields = {field: Text() for field in self.model.fields}
        self.radio_button_group = RadioButtons(
            description="When:",
            options=["All", "30 Days", "24 Hours", "1 Year", "1 Week", "1 Hour"],
        )
        self.refresh_button = Button(description="Refresh")
        date_buttons = VBox([self.radio_button_group, self.refresh_button])
        self.since_widget = DatetimePicker()
        self.until_widget = DatetimePicker()
        date_range = HBox(
            [
                Label(value="Date range:"),
                self.since_widget,
                Label(value="-"),
                self.until_widget,
            ]
        )

        grid_children = []
        for field, text in self._fields.items():
            grid_children.append(Label(value=f"{field}:"))
            grid_children.append(text)

        text_grid = GridBox(children=grid_children, layout=Layout(grid_template_columns="30% 70%"))

        text_input = VBox([date_range, text_grid])
        children = (date_buttons, text_input)
        if self.model.text_search_supported:
            full_text_label = Label("Full Text Search:")
            self.text_search_input = Text()
            text_grid.children += (full_text_label, self.text_search_input)
            self.text_search_input.observe(self._on_text_view_changed, "value")
            self.model.events.text.connect(self._on_text_model_changed)

        super().__init__(children, **kwargs)

        self.radio_button_group.observe(self._on_radio_button_changed, "value")
        self.refresh_button.on_click(self._on_reload_request)
        self.model.events.reload.connect(self._on_reload)
        self.model.events.query.connect(self._on_reload)

        self.since_widget.observe(self._on_since_view_changed, "value")
        self.model.events.since.connect(self._on_since_model_changed)
        self.until_widget.observe(self._on_until_view_changed, "value")
        self.model.events.until.connect(self._on_until_model_changed)

        # Set these values here so the model picks the values up
        self.model.since = GRACE_HOPPER_BIRTHDAY
        self.model.until = timedelta()
        self.radio_button_group.index = self.radio_button_group.options.index("All")

        for field, text in zip(self.model.fields, self._fields.values()):

            def on_field_text_changed(change, field=field):
                self.model.field_search.update({field: change["new"]})

            text.observe(on_field_text_changed, "value")

        self.model.events.field_search_updated.connect(self._on_field_search_updated)

    def _on_radio_button_changed(self, change):
        if change["new"] == "30 Days":
            self.model.since = timedelta(days=-30)
            self.model.until = timedelta()
        elif change["new"] == "24 Hours":
            self.model.since = timedelta(days=-1)
            self.model.until = timedelta()
        elif change["new"] == "1 Year":
            self.model.since = timedelta(days=-365)
            self.model.until = timedelta()
        elif change["new"] == "1 Week":
            self.model.since = timedelta(days=-7)
            self.model.until = timedelta()
        elif change["new"] == "1 Hour":
            self.model.since = timedelta(hours=-1)
            self.model.until = timedelta()
        elif change["new"] == "All":
            self.model.since = GRACE_HOPPER_BIRTHDAY
            self.model.until = timedelta()

    def _on_reload_request(self, event):
        self.model.request_reload()

    def _on_reload(self, event):
        now = self._now()
        if isinstance(self.model.since, timedelta):
            with _blocked(self.since_widget, self._on_since_view_changed, names="value"):
                self.since_widget.value = now + self.model.since
        if isinstance(self.model.until, timedelta):
            with _blocked(self.until_widget, self._on_until_view_changed, names="value"):
                self.until_widget.value = now + self.model.until

    def _on_since_view_changed(self, change):
        self.model.since = change["new"]

    def _on_since_model_changed(self, event):
        now = self._now()
        if isinstance(event.date, timedelta):
            new_datetime = now + event.date
            if event.date == timedelta(hours=-1):
                self.radio_button_group.index = self.radio_button_group.options.index("1 Hour")
            elif event.date == timedelta(days=-1):
                self.radio_button_group.index = self.radio_button_group.options.index("24 Hours")
            elif event.date == timedelta(days=-7):
                self.radio_button_group.index = self.radio_button_group.options.index("1 Week")
            elif event.date == timedelta(days=-30):
                self.radio_button_group.index = self.radio_button_group.options.index("30 Days")
            elif event.date == timedelta(days=-365):
                self.radio_button_group.index = self.radio_button_group.options.index("1 Year")
            else:
                pass
        else:
            if event.date == GRACE_HOPPER_BIRTHDAY:
                self.radio_button_group.index = self.radio_button_group.options.index("All")
            else:
                self.radio_button_group.index = None
            new_datetime = event.date
        with _blocked(self.since_widget, self._on_since_view_changed, names="value"):
            self.since_widget.value = new_datetime
        with _blocked(self.until_widget, self._on_until_view_changed, names="value"):
            self.until_widget.value = now

    def _on_until_view_changed(self, change):
        self.model.until = change["new"]

    def _on_until_model_changed(self, event):
        if not isinstance(event.date, timedelta):
            self.radio_button_group.index = None
            with _blocked(self.until_widget, self._on_until_view_changed, names="value"):
                self.until_widget.value = event.date
        else:
            with _blocked(self.until_widget, self._on_until_view_changed, names="value"):
                self.until_widget.value = event.date + self._now()

    def _on_text_view_changed(self, change):
        self.model.text = change["new"]

    def _on_text_model_changed(self, event):
        self.text_search_input.value = event.text

    def _on_field_search_updated(self, event):
        for k, v in event.update.items():
            text_widget = self._fields[k]
            text_widget.value = v

    @staticmethod
    def _now():
        return datetime.now(tz=LOCAL_TIMEZONE).replace(second=0, microsecond=0)


@contextlib.contextmanager
def _blocked(widget, handler, names=All, type="change"):
    "Block signals from this object inside the context."
    widget.unobserve(handler, names, type)
    try:
        yield
    finally:
        widget.observe(handler, names, type)


GRACE_HOPPER_BIRTHDAY = datetime(1906, 12, 9, tzinfo=LOCAL_TIMEZONE)
