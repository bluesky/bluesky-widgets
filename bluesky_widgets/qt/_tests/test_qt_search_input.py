from datetime import datetime, timedelta
import time
import pytest
from qtpy.QtCore import QDateTime
from ...qt.search import QtSearchInput, ADA_LOVELACE_BIRTHDAY, as_qdatetime
from ...models.search import SearchInput, LOCAL_TIMEZONE


def as_datetime(qdatetime):
    assert isinstance(qdatetime, QDateTime)
    return QDateTime.toPython(qdatetime).replace(tzinfo=LOCAL_TIMEZONE)


def datetime_round_trip(dt):
    return as_datetime(as_qdatetime(dt))


def test_datetime_and_QDateTime_round_trip():
    """
    Converting datetime -> QDateTime -> datetime should round trip.

    Test on a recent time (now) and an old time (ADA_LOVELACE_BIRTHDAY).
    """
    # Current time with only seconds resolution
    now = datetime.now(LOCAL_TIMEZONE).replace(microsecond=0)
    assert datetime_round_trip(now) == now
    assert datetime_round_trip(ADA_LOVELACE_BIRTHDAY) == ADA_LOVELACE_BIRTHDAY


def test_initial_state(qtbot):
    "Check that 'All' is checked and since/until are set as expected."
    model = SearchInput()
    view = QtSearchInput(model)
    TOLERANCE = timedelta(seconds=10)

    # Check state of model...
    assert model.since == ADA_LOVELACE_BIRTHDAY
    # ...and view.
    actual_since = as_datetime(view.since_widget.dateTime())
    assert actual_since == ADA_LOVELACE_BIRTHDAY

    assert model.until == timedelta(0)
    actual_until = as_datetime(view.until_widget.dateTime())
    assert actual_until - datetime.now(LOCAL_TIMEZONE) < TOLERANCE

    # Verify that 'All' radio button is checked.
    assert view.all_widget.isChecked()


def test_initial_state_with_fields(qtbot):
    "Check that QLineEdits show for each field."
    model = SearchInput(fields=["field_1", "field_2"])
    view = QtSearchInput(model)

    assert view.field_text_edit
    assert list(view.field_text_edit.keys()) == model.fields
    for field, text_edit in view.field_text_edit.items():
        assert text_edit.text() == ""


def test_time_input_absolute_from_model(qtbot):
    "Set the model to a datetime and verify that the view updates."
    model = SearchInput()
    view = QtSearchInput(model)

    # Set since.
    expected_since = datetime(1980, 2, 2, tzinfo=LOCAL_TIMEZONE)
    model.since = expected_since
    assert model.since == expected_since
    # Set with naive datetime, should be silently converted to local time.
    model.since = expected_since.replace(tzinfo=None)  # naive
    assert model.since == expected_since
    actual_since = as_datetime(view.since_widget.dateTime())
    assert actual_since == expected_since

    # Set until.
    expected_until = datetime(1986, 11, 15, tzinfo=LOCAL_TIMEZONE)
    model.until = expected_until
    assert model.until == expected_until
    # Set with naive datetime, should be silently converted to local time.
    model.until = expected_until.replace(tzinfo=None)  # naive
    assert model.until == expected_until
    actual_until = as_datetime(view.until_widget.dateTime())
    assert actual_until == expected_until


def test_time_input_absolute_from_datetime_picker(qtbot):
    "Set the view QDateTime inputs and verify that the model updates."
    model = SearchInput()
    view = QtSearchInput(model)

    # Set since.
    expected_since = datetime(1980, 2, 2, tzinfo=LOCAL_TIMEZONE)
    view.since_widget.setDateTime(as_qdatetime(expected_since))
    actual_since = as_datetime(view.since_widget.dateTime())
    assert actual_since == expected_since

    # Set until.
    expected_until = datetime(1986, 11, 15, tzinfo=LOCAL_TIMEZONE)
    view.until_widget.setDateTime(as_qdatetime(expected_until))
    actual_until = as_datetime(view.until_widget.dateTime())
    assert actual_until == expected_until


# timedeltas and attribute name of corresponding QRadioButton on QtSearchInput
DELTAS_AND_BUTTONS = [
    (timedelta(hours=-1), "hour_widget"),
    (timedelta(days=-1), "today_widget"),
    (timedelta(weeks=-1), "week_widget"),
    (timedelta(days=-30), "month_widget"),
    (timedelta(days=-365), "year_widget"),
]


@pytest.mark.parametrize("delta, radio_button", DELTAS_AND_BUTTONS)
def test_time_input_relative_from_model(qtbot, delta, radio_button):
    "Set the model to a timedelta and verify that the view updates."
    model = SearchInput()
    view = QtSearchInput(model)
    TOLERANCE = timedelta(seconds=1)

    # Set since.
    expected_since = datetime.now(LOCAL_TIMEZONE) + delta
    model.since = delta
    actual_since = as_datetime(view.since_widget.dateTime())
    assert abs(actual_since - expected_since) < TOLERANCE

    # And until updates automatically.
    expected_until = datetime.now(LOCAL_TIMEZONE)
    actual_until = as_datetime(view.until_widget.dateTime())
    assert abs(actual_until - expected_until) < TOLERANCE

    # And a radio button is checked.
    radio_button_widget = getattr(view, radio_button)
    assert radio_button_widget.isChecked()


@pytest.mark.parametrize("delta, radio_button", DELTAS_AND_BUTTONS)
def test_time_input_from_radio_buttons(qtbot, delta, radio_button):
    "Check the radio buttons in the view and verify that the model updates."
    model = SearchInput()
    view = QtSearchInput(model)
    TOLERANCE = timedelta(seconds=1)

    # Set radio button.
    radio_button_widget = getattr(view, radio_button)
    radio_button_widget.setChecked(True)

    # Check since.
    expected_since = datetime.now(LOCAL_TIMEZONE) + delta
    actual_since = as_datetime(view.since_widget.dateTime())
    assert abs(actual_since - expected_since) < TOLERANCE

    # Check until.
    expected_until = datetime.now(LOCAL_TIMEZONE)
    actual_until = as_datetime(view.until_widget.dateTime())
    assert abs(actual_until - expected_until) < TOLERANCE

    # Additionally, when the model reloads new results, the QDateTime widets
    # should update, reevaluating their relative times with respect to the
    # current time.
    time.sleep(1)
    model.request_reload()

    # Since and until should update with respect to current time.
    new_actual_since = as_datetime(view.since_widget.dateTime())
    new_actual_until = as_datetime(view.until_widget.dateTime())
    assert actual_since != new_actual_since
    assert actual_until != new_actual_until

    # And button should still be checked.
    assert radio_button_widget.isChecked()
