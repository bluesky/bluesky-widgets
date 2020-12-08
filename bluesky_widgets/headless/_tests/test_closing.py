import matplotlib.pyplot as plt


from ...models.plot_specs import FigureSpec, AxesSpec
from ..figures import HeadlessFigure


def test_closing():
    axes = AxesSpec()
    model = FigureSpec(axes=(axes,), title="test")
    view = HeadlessFigure(model)
    assert plt.fignum_exists(view.figure.number)
    view.close_figure()
    assert not plt.fignum_exists(view.figure.number)
