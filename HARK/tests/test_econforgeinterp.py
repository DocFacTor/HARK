import unittest
import numpy as np

from HARK.interpolation import LinearInterp, BilinearInterp
from HARK.econforgeinterp import LinearFast
from HARK.core import distance_metric


class CompareLinearInterp(unittest.TestCase):
    """ 
    Compares output and properties with the basic linearinterp
    """

    def setUp(self):

        self.n_grid_points = 100
        self.n_eval_points = 3

    def compare_output(self, x, y, eval_points):

        h_interp = LinearInterp(x, y, lower_extrap=True)
        e_interp = LinearFast(y, [x])

        # Function evaluation
        h_vals = h_interp(eval_points)
        e_vals = e_interp(eval_points)
        self.assertTrue(np.allclose(h_vals, e_vals))

        # Derivative
        h_der = h_interp._der(eval_points)
        e_der = e_interp.gradient(eval_points)[0]
        self.assertTrue(np.allclose(h_der, e_der))

    def test_outputs(self):
        """
        Tests that function calls using the base hark and
        econforge implementations return the same.
        """
        # Square function
        x = np.linspace(0, 10, self.n_grid_points)
        y = np.power(x, 2)

        # Interpolation
        in_points = np.linspace(2, 8, self.n_eval_points)
        self.compare_output(x, y, in_points)

        # Extrapolation
        ex_points = np.linspace(-10, 20, self.n_eval_points)
        self.compare_output(x, y, ex_points)

    def test_metric(self):
        """
        Tests that the interpolator metric called on a pair of
        interpolator objects is the same for hark and econforge
        interps
        """
        n_points = 10

        x0 = np.exp(np.linspace(0, 1, n_points))
        y0 = np.sin(x0)

        x1 = np.linspace(-10, 20, n_points)
        y1 = 0.5 * x1 + 2

        # Distance with HARK
        h_dist = distance_metric(LinearInterp(x0, y0), LinearInterp(x1, y1))
        # Distance with econforge
        e_dist = distance_metric(LinearFast(y0, [x0]), LinearFast(y1, [x1]))

        self.assertAlmostEqual(h_dist, e_dist)


class CompareBilinearInterp(unittest.TestCase):
    """ 
    Compares output and properties with the basic linearinterp
    """

    def setUp(self):

        self.n_grid_points = 100
        self.n_eval_points = 3

    def compare_output(self, x, y, z, eval_x, eval_y):

        h_interp = BilinearInterp(z, x, y)
        e_interp = LinearFast(z, [x, y])

        # Function value
        h_vals = h_interp(eval_x, eval_y)
        e_vals = e_interp(eval_x, eval_y)
        self.assertTrue(np.allclose(h_vals, e_vals))

        # Derivatives
        h_grad = [
            h_interp.derivativeX(eval_x, eval_y),
            h_interp.derivativeY(eval_x, eval_y),
        ]
        e_grad = e_interp.gradient(eval_x, eval_y)

        for i, der in enumerate(h_grad):
            self.assertTrue(np.allclose(der, e_grad[i]))

    def test_outputs(self):
        """
        Tests that function calls using the base hark and
        econforge implementations return the same.
        """
        # Sum of squares function
        x_grid = np.linspace(0, 10, self.n_grid_points)
        y_grid = np.linspace(0, 10, self.n_grid_points)

        x_tiled, y_tiled = np.meshgrid(x_grid, y_grid, indexing="ij")

        z = np.power(x_tiled, 2) + np.power(y_tiled, 2)

        # Interpolation
        x_in, y_in = np.meshgrid(
            np.linspace(2, 8, self.n_eval_points),
            np.linspace(2, 8, self.n_eval_points),
            indexing="ij",
        )
        self.compare_output(x_grid, y_grid, z, x_in, y_in)

        # Extrapolation
        x_ex, y_ex = np.meshgrid(
            np.linspace(-10, 20, self.n_eval_points),
            np.linspace(-10, 20, self.n_eval_points),
            indexing="ij",
        )
        self.compare_output(x_grid, y_grid, z, x_ex, y_ex)

    def test_metric(self):
        """
        Tests that the interpolator metric called on a pair of
        interpolator objects is the same for hark and econforge
        interps
        """
        n_points = 10

        x0 = np.exp(np.linspace(0, 1, n_points))
        y0 = np.linspace(3, 4, n_points)
        x0_t, y0_t = np.meshgrid(x0, y0, indexing="ij")
        z0 = np.sin(x0_t) + y0_t

        x1 = np.linspace(-10, 20, n_points)
        y1 = 0.5 * x1 + 2
        x1_t, y1_t = np.meshgrid(x1, y1, indexing="ij")
        z1 = x1_t + y1_t

        # Distance with HARK
        h_dist = distance_metric(BilinearInterp(z0, x0, y0), BilinearInterp(z1, x1, y1))
        # Distance with econforge
        e_dist = distance_metric(LinearFast(z0, [x0, y0]), LinearFast(z1, [x1, y1]))

        self.assertAlmostEqual(h_dist, e_dist)


# Derivative tests


class Check1DDerivatives(unittest.TestCase):
    """ 
    Checks derivatives in a 1D interpolator
    """

    def test_linear(self):

        # A linear function on a non-uniform grid
        x = np.exp(np.linspace(0, 2, 6))
        y0 = 2
        slope = 1.0
        y = y0 + slope * x

        interp = LinearFast(y, [x])

        eval_points = np.array([1.5, 2.5, 3.5, 4.5])

        grad = interp.gradient(eval_points)[0]
        result = np.ones_like(eval_points) * slope

        self.assertTrue(np.allclose(grad, result))

    def test_nonlinear(self):

        # A non linear function on uniform grid
        x = np.linspace(-10, 10, 21) * (1 / 2) * np.pi
        y = np.sin(x)
        interp = LinearFast(y, [x])

        eval_points = np.array([-1, -0.5, 0, 0.5, 1]) * np.pi
        grad = interp.gradient(eval_points)[0]

        # 1-order must be + or - pi/2
        result = np.array([-1, -1, 1, 1, -1]) * 2 / np.pi

        self.assertTrue(np.allclose(grad, result))

    def test_nonlinear_approx(self):

        # A non linear function on uniform grid
        x = np.linspace(-10, 10, 10000)
        y = np.power(x, 3)
        interp = LinearFast(y, [x])
        eval_points = np.linspace(-5, 5, 10)

        grad = interp.gradient(eval_points)[0]
        result = np.power(eval_points, 2) * 3.0

        self.assertTrue(np.allclose(grad, result, atol=0.02))


class Check2DDerivatives(unittest.TestCase):
    """ 
    Checks derivatives in a 2D interpolator
    """

    def test_linear(self):

        # A linear function on a non-uniform grid
        x = np.exp(np.linspace(0, 2, 6))
        y = np.power(np.linspace(0, 5, 10), 2)
        x_tiled, y_tiled = np.meshgrid(x, y, indexing="ij")

        inter = 1
        slope_x = 2
        slope_y = -3
        z = inter + slope_x * x_tiled + slope_y * y_tiled

        interp = LinearFast(z, [x, y])

        # Evaluation points
        n_eval = 7
        x_ev, y_ev = np.meshgrid(
            np.linspace(-20, 20, n_eval), np.linspace(5, -5, n_eval), indexing="ij"
        )

        # Gradient
        grad = interp.gradient(x_ev, y_ev)

        # (1,0) must be x slope
        # (0,1) must be y slope
        self.assertTrue(np.allclose(grad[0], np.ones_like(x_ev) * slope_x))
        self.assertTrue(np.allclose(grad[1], np.ones_like(y_ev) * slope_y))

    def test_nonlinear_approx(self):

        # A non linear function on uniform grid
        n_grid = 100
        x = np.linspace(1, 5, n_grid)
        y = np.linspace(1, 5, n_grid)

        x_tiled, y_tiled = np.meshgrid(x, y, indexing="ij")
        z = np.sin(x_tiled) * np.log(y_tiled)

        interp = LinearFast(z, [x, y])

        # Evaluation points
        n_eval = 15
        x_ev, y_ev = np.meshgrid(
            np.linspace(2, 4, n_eval), np.linspace(4, 2, n_eval), indexing="ij",
        )

        # Get function and 1st derivatives
        grad = interp.gradient(x_ev, y_ev)

        # (1,0) must be cos(x) * ln(y)
        self.assertTrue(np.allclose(grad[0], np.cos(x_ev) * np.log(y_ev), atol=0.02))
        # (0,1) must be sin(x) / y
        self.assertTrue(np.allclose(grad[1], np.sin(x_ev) * (1 / y_ev), atol=0.02))