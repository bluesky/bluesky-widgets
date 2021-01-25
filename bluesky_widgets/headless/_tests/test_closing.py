import matplotlib.pyplot as plt


from ...models.plot_specs import Figure, Axes
from ..figures import HeadlessFigure


def test_closing():
    axes = Axes()
    model = Figure(axes=(axes,), title="test")
    view = HeadlessFigure(model)
    assert plt.fignum_exists(view.figure.number)
    view.close_figure()
    assert not plt.fignum_exists(view.figure.number)
