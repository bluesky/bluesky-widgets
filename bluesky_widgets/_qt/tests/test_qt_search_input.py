from datetime import datetime, timedelta
import time
import pytest
from qtpy.QtCore import QDateTime
from ...qt.search_input import QtSearchInput
from ...components.search.search_input import SearchInput


def as_qdatetime(datetime):
    "Create QDateTime set as specified by datetime."
    qdatetime = QDateTime()
    qdatetime.setSecsSinceEpoch(datetime.timestamp())
    return qdatetime


def test_time_input_absolute_from_model(qtbot):
    "Set the model to a datetime and verify that the view updates."
    model = SearchInput()
    view = QtSearchInput(model)

    # Set since.
    expected_since = datetime(1980, 2, 2)
    model.since = expected_since
    actual_since = datetime.fromtimestamp(view.since_widget.dateTime().toSecsSinceEpoch())
    assert actual_since == expected_since

    # Set until.
    expected_until = datetime(1986, 11, 15)
    model.until = expected_until
    actual_until = datetime.fromtimestamp(view.until_widget.dateTime().toSecsSinceEpoch())
    assert actual_until == expected_until


def test_time_input_absolute_from_datetime_picker(qtbot):
    "Set the view QDateTime inputs and verify that the model updates."
    model = SearchInput()
    view = QtSearchInput(model)

    # Set since.
    expected_since = datetime(1980, 2, 2)
    view.since_widget.setDateTime(as_qdatetime(expected_since))
    actual_since = datetime.fromtimestamp(view.since_widget.dateTime().toSecsSinceEpoch())
    assert actual_since == expected_since

    # Set until.
    expected_until = datetime(1986, 11, 15)
    view.until_widget.setDateTime(as_qdatetime(expected_until))
    actual_until = datetime.fromtimestamp(view.until_widget.dateTime().toSecsSinceEpoch())
    assert actual_until == expected_until


# timedeltas and attribute name of corresponding QRadioButton on QtSearchInput
DELTAS_AND_BUTTONS = [
        (timedelta(hours=-1), 'hour_widget'),
        (timedelta(days=-1), 'today_widget'),
        (timedelta(weeks=-1), 'week_widget'),
        (timedelta(days=-30), 'month_widget'),
        (timedelta(days=-365), 'year_widget'),
]


@pytest.mark.parametrize('delta, radio_button', DELTAS_AND_BUTTONS)
def test_time_input_relative_from_model(qtbot, delta, radio_button):
    "Set the model to a timedelta and verify that the view updates."
    model = SearchInput()
    view = QtSearchInput(model)
    TOLERANCE = timedelta(seconds=1)

    # Set since.
    expected_since = datetime.now() + delta
    model.since = delta
    actual_since = datetime.fromtimestamp(view.since_widget.dateTime().toSecsSinceEpoch())
    assert abs(actual_since - expected_since) < TOLERANCE

    # And until updates automatically.
    expected_until = datetime.now()
    actual_until = datetime.fromtimestamp(view.until_widget.dateTime().toSecsSinceEpoch())
    assert abs(actual_until - expected_until) < TOLERANCE

    # And a radio button is checked.
    radio_button_widget = getattr(view, radio_button)
    radio_button_widget.isChecked()


@pytest.mark.parametrize('delta, radio_button', DELTAS_AND_BUTTONS)
def test_time_input_from_radio_buttons(qtbot, delta, radio_button):
    "Check the radio buttons in the view and verify that the model updates."
    model = SearchInput()
    view = QtSearchInput(model)
    TOLERANCE = timedelta(seconds=1)

    # Set radio button.
    radio_button_widget = getattr(view, radio_button)
    radio_button_widget.setChecked(True)

    # Check since.
    expected_since = datetime.now() + delta
    actual_since = datetime.fromtimestamp(view.since_widget.dateTime().toSecsSinceEpoch())
    assert abs(actual_since - expected_since) < TOLERANCE

    # Check until.
    expected_until = datetime.now()
    actual_until = datetime.fromtimestamp(view.until_widget.dateTime().toSecsSinceEpoch())
    assert abs(actual_until - expected_until) < TOLERANCE

    # Additionally, when the model reloads new results, the QDateTime widets
    # should update, reevaluating their relative times with respect to the
    # current time.
    time.sleep(1)
    model.request_reload()

    # Since and until should update with respect to current time.
    new_actual_since = datetime.fromtimestamp(view.since_widget.dateTime().toSecsSinceEpoch())
    new_actual_until = datetime.fromtimestamp(view.until_widget.dateTime().toSecsSinceEpoch())
    assert actual_since != new_actual_since
    assert actual_until != new_actual_until

    # And button should still be checked.
    radio_button_widget.isChecked()
