"""
This file contains classes and functions for representing, solving, and simulating
agents who must allocate their resources among consumption, saving in a risk-free
asset (with a low return), and saving in a risky asset (with higher average return).
"""

from copy import deepcopy

import numpy as np

from HARK import NullFunc
from HARK.ConsumptionSaving.ConsIndShockModel import (
    IndShockConsumerType,
    init_idiosyncratic_shocks,
)
from HARK.ConsumptionSaving.ConsRiskyAssetModel import RiskyAssetConsumerType
from HARK.distribution import expected
from HARK.interpolation import (
    BilinearInterp,
    ConstantFunction,
    CubicInterp,
    IdentityFunction,
    LinearInterp,
    LinearInterpOnInterp1D,
    MargValueFuncCRRA,
    ValueFuncCRRA,
)
from HARK.metric import MetricObject
from HARK.rewards import UtilityFuncCRRA


# Define a class to represent the single period solution of the portfolio choice problem
class PortfolioSolution(MetricObject):
    """
    A class for representing the single period solution of the portfolio choice model.

    Parameters
    ----------
    cFuncAdj : Interp1D
        Consumption function over normalized market resources when the agent is able
        to adjust their portfolio shares.
    ShareFuncAdj : Interp1D
        Risky share function over normalized market resources when the agent is able
        to adjust their portfolio shares.
    vFuncAdj : ValueFuncCRRA
        Value function over normalized market resources when the agent is able to
        adjust their portfolio shares.
    vPfuncAdj : MargValueFuncCRRA
        Marginal value function over normalized market resources when the agent is able
        to adjust their portfolio shares.
    cFuncFxd : Interp2D
        Consumption function over normalized market resources and risky portfolio share
        when the agent is NOT able to adjust their portfolio shares, so they are fixed.
    ShareFuncFxd : Interp2D
        Risky share function over normalized market resources and risky portfolio share
        when the agent is NOT able to adjust their portfolio shares, so they are fixed.
        This should always be an IdentityFunc, by definition.
    vFuncFxd : ValueFuncCRRA
        Value function over normalized market resources and risky portfolio share when
        the agent is NOT able to adjust their portfolio shares, so they are fixed.
    dvdmFuncFxd : MargValueFuncCRRA
        Marginal value of mNrm function over normalized market resources and risky
        portfolio share when the agent is NOT able to adjust their portfolio shares,
        so they are fixed.
    dvdsFuncFxd : MargValueFuncCRRA
        Marginal value of Share function over normalized market resources and risky
        portfolio share when the agent is NOT able to adjust their portfolio shares,
        so they are fixed.
    aGrid: np.array
        End-of-period-assets grid used to find the solution.
    Share_adj: np.array
        Optimal portfolio share associated with each aGrid point.
    EndOfPrddvda_adj: np.array
        Marginal value of end-of-period resources associated with each aGrid
        point.
    ShareGrid: np.array
        Grid for the portfolio share that is used to solve the model.
    EndOfPrddvda_fxd: np.array
        Marginal value of end-of-period resources associated with each
        (aGrid x sharegrid) combination, for the agent who can not adjust his
        portfolio.
    AdjustPrb: float
        Probability that the agent will be able to adjust his portfolio
        next period.
    """

    distance_criteria = ["vPfuncAdj"]

    def __init__(
        self,
        cFuncAdj=None,
        ShareFuncAdj=None,
        vFuncAdj=None,
        vPfuncAdj=None,
        cFuncFxd=None,
        ShareFuncFxd=None,
        vFuncFxd=None,
        dvdmFuncFxd=None,
        dvdsFuncFxd=None,
        aGrid=None,
        Share_adj=None,
        EndOfPrddvda_adj=None,
        ShareGrid=None,
        EndOfPrddvda_fxd=None,
        EndOfPrddvds_fxd=None,
        AdjPrb=None,
    ):
        # Change any missing function inputs to NullFunc
        if cFuncAdj is None:
            cFuncAdj = NullFunc()
        if cFuncFxd is None:
            cFuncFxd = NullFunc()
        if ShareFuncAdj is None:
            ShareFuncAdj = NullFunc()
        if ShareFuncFxd is None:
            ShareFuncFxd = NullFunc()
        if vFuncAdj is None:
            vFuncAdj = NullFunc()
        if vFuncFxd is None:
            vFuncFxd = NullFunc()
        if vPfuncAdj is None:
            vPfuncAdj = NullFunc()
        if dvdmFuncFxd is None:
            dvdmFuncFxd = NullFunc()
        if dvdsFuncFxd is None:
            dvdsFuncFxd = NullFunc()

        # Set attributes of self
        self.cFuncAdj = cFuncAdj
        self.cFuncFxd = cFuncFxd
        self.ShareFuncAdj = ShareFuncAdj
        self.ShareFuncFxd = ShareFuncFxd
        self.vFuncAdj = vFuncAdj
        self.vFuncFxd = vFuncFxd
        self.vPfuncAdj = vPfuncAdj
        self.dvdmFuncFxd = dvdmFuncFxd
        self.dvdsFuncFxd = dvdsFuncFxd
        self.aGrid = aGrid
        self.Share_adj = Share_adj
        self.EndOfPrddvda_adj = EndOfPrddvda_adj
        self.ShareGrid = ShareGrid
        self.EndOfPrddvda_fxd = EndOfPrddvda_fxd
        self.EndOfPrddvds_fxd = EndOfPrddvds_fxd
        self.AdjPrb = AdjPrb


class PortfolioConsumerType(RiskyAssetConsumerType):
    """
    A consumer type with a portfolio choice. This agent type has log-normal return
    factors. Their problem is defined by a coefficient of relative risk aversion,
    intertemporal discount factor, risk-free interest factor, and time sequences of
    permanent income growth rate, survival probability, and permanent and transitory
    income shock standard deviations (in logs).  The agent may also invest in a risky
    asset, which has a higher average return than the risk-free asset.  He *might*
    have age-varying beliefs about the risky-return; if he does, then "true" values
    of the risky asset's return distribution must also be specified.
    """

    time_inv_ = deepcopy(RiskyAssetConsumerType.time_inv_)
    time_inv_ = time_inv_ + ["AdjustPrb", "DiscreteShareBool"]

    def __init__(self, verbose=False, quiet=False, **kwds):
        params = init_portfolio.copy()
        params.update(kwds)
        kwds = params

        self.PortfolioBool = True

        # Initialize a basic consumer type
        RiskyAssetConsumerType.__init__(self, verbose=verbose, quiet=quiet, **kwds)

        # Set the solver for the portfolio model, and update various constructed attributes
        self.solve_one_period = solve_one_period_ConsPortfolio

    def update(self):
        RiskyAssetConsumerType.update(self)
        self.update_ShareGrid()
        self.update_ShareLimit()

    def update_solution_terminal(self):
        """
        Solves the terminal period of the portfolio choice problem.  The solution is
        trivial, as usual: consume all market resources, and put nothing in the risky
        asset (because you have nothing anyway).

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        # Consume all market resources: c_T = m_T
        cFuncAdj_terminal = IdentityFunction()
        cFuncFxd_terminal = IdentityFunction(i_dim=0, n_dims=2)

        # Risky share is irrelevant-- no end-of-period assets; set to zero
        ShareFuncAdj_terminal = ConstantFunction(0.0)
        ShareFuncFxd_terminal = IdentityFunction(i_dim=1, n_dims=2)

        # Value function is simply utility from consuming market resources
        vFuncAdj_terminal = ValueFuncCRRA(cFuncAdj_terminal, self.CRRA)
        vFuncFxd_terminal = ValueFuncCRRA(cFuncFxd_terminal, self.CRRA)

        # Marginal value of market resources is marg utility at the consumption function
        vPfuncAdj_terminal = MargValueFuncCRRA(cFuncAdj_terminal, self.CRRA)
        dvdmFuncFxd_terminal = MargValueFuncCRRA(cFuncFxd_terminal, self.CRRA)
        dvdsFuncFxd_terminal = ConstantFunction(
            0.0
        )  # No future, no marg value of Share

        # Construct the terminal period solution
        self.solution_terminal = PortfolioSolution(
            cFuncAdj=cFuncAdj_terminal,
            ShareFuncAdj=ShareFuncAdj_terminal,
            vFuncAdj=vFuncAdj_terminal,
            vPfuncAdj=vPfuncAdj_terminal,
            cFuncFxd=cFuncFxd_terminal,
            ShareFuncFxd=ShareFuncFxd_terminal,
            vFuncFxd=vFuncFxd_terminal,
            dvdmFuncFxd=dvdmFuncFxd_terminal,
            dvdsFuncFxd=dvdsFuncFxd_terminal,
        )
        self.solution_terminal.hNrm = 0.0
        self.solution_terminal.MPCmin = 1.0

    def initialize_sim(self):
        """
        Initialize the state of simulation attributes.  Simply calls the same method
        for IndShockConsumerType, then sets the type of AdjustNow to bool.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        # these need to be set because "post states",
        # but are a control variable and shock, respectively
        self.controls["Share"] = np.zeros(self.AgentCount)
        RiskyAssetConsumerType.initialize_sim(self)

    def sim_birth(self, which_agents):
        """
        Create new agents to replace ones who have recently died; takes draws of
        initial aNrm and pLvl, as in ConsIndShockModel, then sets Share and Adjust
        to zero as initial values.
        Parameters
        ----------
        which_agents : np.array
            Boolean array of size AgentCount indicating which agents should be "born".

        Returns
        -------
        None
        """
        IndShockConsumerType.sim_birth(self, which_agents)

        self.controls["Share"][which_agents] = 0
        # here a shock is being used as a 'post state'
        self.shocks["Adjust"][which_agents] = False

    def get_controls(self):
        """
        Calculates consumption cNrmNow and risky portfolio share ShareNow using
        the policy functions in the attribute solution.  These are stored as attributes.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        cNrmNow = np.zeros(self.AgentCount) + np.nan
        ShareNow = np.zeros(self.AgentCount) + np.nan

        # Loop over each period of the cycle, getting controls separately depending on "age"
        for t in range(self.T_cycle):
            these = t == self.t_cycle

            # Get controls for agents who *can* adjust their portfolio share
            those = np.logical_and(these, self.shocks["Adjust"])
            cNrmNow[those] = self.solution[t].cFuncAdj(self.state_now["mNrm"][those])
            ShareNow[those] = self.solution[t].ShareFuncAdj(
                self.state_now["mNrm"][those]
            )

            # Get Controls for agents who *can't* adjust their portfolio share
            those = np.logical_and(these, np.logical_not(self.shocks["Adjust"]))
            cNrmNow[those] = self.solution[t].cFuncFxd(
                self.state_now["mNrm"][those], ShareNow[those]
            )
            ShareNow[those] = self.solution[t].ShareFuncFxd(
                self.state_now["mNrm"][those], ShareNow[those]
            )

        # Store controls as attributes of self
        self.controls["cNrm"] = cNrmNow
        self.controls["Share"] = ShareNow


def solve_one_period_ConsPortfolio(
    solution_next,
    ShockDstn,
    IncShkDstn,
    RiskyDstn,
    LivPrb,
    DiscFac,
    CRRA,
    Rfree,
    PermGroFac,
    BoroCnstArt,
    aXtraGrid,
    ShareGrid,
    AdjustPrb,
    ShareLimit,
    vFuncBool,
    DiscreteShareBool,
    IndepDstnBool,
):
    """
    Solve one period of a consumption-saving problem with portfolio allocation
    between a riskless and risky asset. This function handles various sub-cases
    or variations on the problem, including the possibility that the agent does
    not necessarily get to update their portfolio share in every period, or that
    they must choose a discrete rather than continuous risky share.

    Parameters
    ----------
    solution_next : PortfolioSolution
        Solution to next period's problem.
    ShockDstn : Distribution
        Joint distribution of permanent income shocks, transitory income shocks,
        and risky returns.  This is only used if the input IndepDstnBool is False,
        indicating that income and return distributions can't be assumed to be
        independent.
    IncShkDstn : Distribution
        Discrete distribution of permanent income shocks and transitory income
        shocks. This is only used if the input IndepDstnBool is True, indicating
        that income and return distributions are independent.
    RiskyDstn : Distribution
       Distribution of risky asset returns. This is only used if the input
       IndepDstnBool is True, indicating that income and return distributions
       are independent.
    LivPrb : float
        Survival probability; likelihood of being alive at the beginning of
        the succeeding period.
    DiscFac : float
        Intertemporal discount factor for future utility.
    CRRA : float
        Coefficient of relative risk aversion.
    Rfree : float
        Risk free interest factor on end-of-period assets.
    PermGroFac : float
        Expected permanent income growth factor at the end of this period.
    BoroCnstArt: float or None
        Borrowing constraint for the minimum allowable assets to end the
        period with.  In this model, it is *required* to be zero.
    aXtraGrid: np.array
        Array of "extra" end-of-period asset values-- assets above the
        absolute minimum acceptable level.
    ShareGrid : np.array
        Array of risky portfolio shares on which to define the interpolation
        of the consumption function when Share is fixed. Also used when the
        risky share choice is specified as discrete rather than continuous.
    AdjustPrb : float
        Probability that the agent will be able to update his portfolio share.
    ShareLimit : float
        Limiting lower bound of risky portfolio share as mNrm approaches infinity.
    vFuncBool: boolean
        An indicator for whether the value function should be computed and
        included in the reported solution.
    DiscreteShareBool : bool
        Indicator for whether risky portfolio share should be optimized on the
        continuous [0,1] interval using the FOC (False), or instead only selected
        from the discrete set of values in ShareGrid (True).  If True, then
        vFuncBool must also be True.
    IndepDstnBool : bool
        Indicator for whether the income and risky return distributions are in-
        dependent of each other, which can speed up the expectations step.

    Returns
    -------
    solution_now : PortfolioSolution
        Solution to this period's problem.
    """
    # Make sure the individual is liquidity constrained.  Allowing a consumer to
    # borrow *and* invest in an asset with unbounded (negative) returns is a bad mix.
    if BoroCnstArt != 0.0:
        raise ValueError("PortfolioConsumerType must have BoroCnstArt=0.0!")

    # Make sure that if risky portfolio share is optimized only discretely, then
    # the value function is also constructed (else this task would be impossible).
    if DiscreteShareBool and (not vFuncBool):
        raise ValueError(
            "PortfolioConsumerType requires vFuncBool to be True when DiscreteShareBool is True!"
        )

    # Define the current period utility function and effective discount factor
    uFunc = UtilityFuncCRRA(CRRA)
    DiscFacEff = DiscFac * LivPrb  # "effective" discount factor

    # Unpack next period's solution for easier access
    vPfuncAdj_next = solution_next.vPfuncAdj
    dvdmFuncFxd_next = solution_next.dvdmFuncFxd
    dvdsFuncFxd_next = solution_next.dvdsFuncFxd
    vFuncAdj_next = solution_next.vFuncAdj
    vFuncFxd_next = solution_next.vFuncFxd

    # Set a flag for whether the natural borrowing constraint is zero, which
    # depends on whether the smallest transitory income shock is zero
    BoroCnstNat_iszero = np.min(IncShkDstn.atoms[1]) == 0.0

    # Prepare to calculate end-of-period marginal values by creating an array
    # of market resources that the agent could have next period, considering
    # the grid of end-of-period assets and the distribution of shocks he might
    # experience next period.

    # Unpack the risky return shock distribution
    Risky_next = RiskyDstn.atoms
    RiskyMax = np.max(Risky_next)
    RiskyMin = np.min(Risky_next)

    # Perform an alternate calculation of the absolute patience factor when
    # returns are risky. This uses the Merton-Samuelson limiting risky share,
    # which is what's relevant as mNrm goes to infinity.
    def calc_Radj(R):
        Rport = ShareLimit * R + (1.0 - ShareLimit) * Rfree
        return Rport ** (1.0 - CRRA)

    R_adj = expected(calc_Radj, RiskyDstn)[0]
    PatFac = (DiscFacEff * R_adj) ** (1.0 / CRRA)
    MPCminNow = 1.0 / (1.0 + PatFac / solution_next.MPCmin)

    # Also perform an alternate calculation for human wealth under risky returns
    def calc_hNrm(S):
        Risky = S["Risky"]
        PermShk = S["PermShk"]
        TranShk = S["TranShk"]
        G = PermGroFac * PermShk
        Rport = ShareLimit * Risky + (1.0 - ShareLimit) * Rfree
        hNrm = (G / Rport**CRRA) * (TranShk + solution_next.hNrm)
        return hNrm

    # This correctly accounts for risky returns and risk aversion
    hNrmNow = expected(calc_hNrm, ShockDstn) / R_adj

    # This basic equation works if there's no correlation among shocks
    # hNrmNow = (PermGroFac/Rfree)*(1 + solution_next.hNrm)

    # Set the terms of the limiting linear consumption function as mNrm goes to infinity
    cFuncLimitIntercept = MPCminNow * hNrmNow
    cFuncLimitSlope = MPCminNow

    # bNrm represents R*a, balances after asset return shocks but before income.
    # This just uses the highest risky return as a rough shifter for the aXtraGrid.
    if BoroCnstNat_iszero:
        aNrmGrid = aXtraGrid
        bNrmGrid = np.insert(RiskyMax * aXtraGrid, 0, RiskyMin * aXtraGrid[0])
    else:
        # Add an asset point at exactly zero
        aNrmGrid = np.insert(aXtraGrid, 0, 0.0)
        bNrmGrid = RiskyMax * np.insert(aXtraGrid, 0, 0.0)

    # Get grid and shock sizes, for easier indexing
    aNrmCount = aNrmGrid.size
    ShareCount = ShareGrid.size

    # If the income shock distribution is independent from the risky return distribution,
    # then taking end-of-period expectations can proceed in a two part process: First,
    # construct an "intermediate" value function by integrating out next period's income
    # shocks, *then* compute end-of-period expectations by integrating out return shocks.
    # This method is lengthy to code, but can be significantly faster.
    if IndepDstnBool:
        # Make tiled arrays to calculate future realizations of mNrm and Share when integrating over IncShkDstn
        bNrmNext, ShareNext = np.meshgrid(bNrmGrid, ShareGrid, indexing="ij")

        # Define functions that are used internally to evaluate future realizations
        def calc_mNrm_next(S, b):
            """
            Calculate future realizations of market resources mNrm from the income
            shock distribution S and normalized bank balances b.
            """
            return b / (S["PermShk"] * PermGroFac) + S["TranShk"]

        def calc_dvdm_next(S, b, z):
            """
            Evaluate realizations of marginal value of market resources next period,
            based on the income distribution S, values of bank balances bNrm, and
            values of the risky share z.
            """
            mNrm_next = calc_mNrm_next(S, b)
            dvdmAdj_next = vPfuncAdj_next(mNrm_next)

            if AdjustPrb < 1.0:
                # Expand to the same dimensions as mNrm
                Share_next_expanded = z + np.zeros_like(mNrm_next)
                dvdmFxd_next = dvdmFuncFxd_next(mNrm_next, Share_next_expanded)
                # Combine by adjustment probability
                dvdm_next = AdjustPrb * dvdmAdj_next + (1.0 - AdjustPrb) * dvdmFxd_next
            else:  # Don't bother evaluating if there's no chance that portfolio share is fixed
                dvdm_next = dvdmAdj_next

            dvdm_next = (S["PermShk"] * PermGroFac) ** (-CRRA) * dvdm_next
            return dvdm_next

        def calc_dvds_next(S, b, z):
            """
            Evaluate realizations of marginal value of risky share next period, based
            on the income distribution S, values of bank balances bNrm, and values of
            the risky share z.
            """
            mNrm_next = calc_mNrm_next(S, b)

            # No marginal value of Share if it's a free choice!
            dvdsAdj_next = np.zeros_like(mNrm_next)

            if AdjustPrb < 1.0:
                # Expand to the same dimensions as mNrm
                Share_next_expanded = z + np.zeros_like(mNrm_next)
                dvdsFxd_next = dvdsFuncFxd_next(mNrm_next, Share_next_expanded)
                # Combine by adjustment probability
                dvds_next = AdjustPrb * dvdsAdj_next + (1.0 - AdjustPrb) * dvdsFxd_next
            else:  # Don't bother evaluating if there's no chance that portfolio share is fixed
                dvds_next = dvdsAdj_next

            dvds_next = (S["PermShk"] * PermGroFac) ** (1.0 - CRRA) * dvds_next
            return dvds_next

        # Calculate end-of-period marginal value of assets and shares at each point
        # in aNrm and ShareGrid. Does so by taking expectation of next period marginal
        # values across income and risky return shocks.

        # Calculate intermediate marginal value of bank balances by taking expectations over income shocks
        dvdb_intermed = expected(calc_dvdm_next, IncShkDstn, args=(bNrmNext, ShareNext))
        dvdbNvrs_intermed = uFunc.derinv(dvdb_intermed, order=(1, 0))
        dvdbNvrsFunc_intermed = BilinearInterp(dvdbNvrs_intermed, bNrmGrid, ShareGrid)
        dvdbFunc_intermed = MargValueFuncCRRA(dvdbNvrsFunc_intermed, CRRA)

        # Calculate intermediate marginal value of risky portfolio share by taking expectations over income shocks
        dvds_intermed = expected(calc_dvds_next, IncShkDstn, args=(bNrmNext, ShareNext))
        dvdsFunc_intermed = BilinearInterp(dvds_intermed, bNrmGrid, ShareGrid)

        # Make tiled arrays to calculate future realizations of bNrm and Share when integrating over RiskyDstn
        aNrmNow, ShareNext = np.meshgrid(aNrmGrid, ShareGrid, indexing="ij")

        # Define functions for calculating end-of-period marginal value
        def calc_EndOfPrd_dvda(S, a, z):
            """
            Compute end-of-period marginal value of assets at values a, conditional
            on risky asset return S and risky share z.
            """
            # Calculate future realizations of bank balances bNrm
            Rxs = S - Rfree  # Excess returns
            Rport = Rfree + z * Rxs  # Portfolio return
            bNrm_next = Rport * a

            # Ensure shape concordance
            z_rep = z + np.zeros_like(bNrm_next)

            # Calculate and return dvda
            EndOfPrd_dvda = Rport * dvdbFunc_intermed(bNrm_next, z_rep)
            return EndOfPrd_dvda

        def calc_EndOfPrddvds(S, a, z):
            """
            Compute end-of-period marginal value of risky share at values a, conditional
            on risky asset return S and risky share z.
            """
            # Calculate future realizations of bank balances bNrm
            Rxs = S - Rfree  # Excess returns
            Rport = Rfree + z * Rxs  # Portfolio return
            bNrm_next = Rport * a

            # Make the shares match the dimension of b, so that it can be vectorized
            z_rep = z + np.zeros_like(bNrm_next)

            # Calculate and return dvds
            EndOfPrd_dvds = Rxs * a * dvdbFunc_intermed(
                bNrm_next, z_rep
            ) + dvdsFunc_intermed(bNrm_next, z_rep)
            return EndOfPrd_dvds

        # Evaluate realizations of value and marginal value after asset returns are realized

        # Calculate end-of-period marginal value of assets by taking expectations
        EndOfPrd_dvda = DiscFacEff * expected(
            calc_EndOfPrd_dvda, RiskyDstn, args=(aNrmNow, ShareNext)
        )
        EndOfPrd_dvdaNvrs = uFunc.derinv(EndOfPrd_dvda)

        # Calculate end-of-period marginal value of risky portfolio share by taking expectations
        EndOfPrd_dvds = DiscFacEff * expected(
            calc_EndOfPrddvds, RiskyDstn, args=(aNrmNow, ShareNext)
        )

        # Make the end-of-period value function if the value function is requested
        if vFuncBool:

            def calc_v_intermed(S, b, z):
                """
                Calculate "intermediate" value from next period's bank balances, the
                income shocks S, and the risky asset share.
                """
                mNrm_next = calc_mNrm_next(S, b)

                vAdj_next = vFuncAdj_next(mNrm_next)
                if AdjustPrb < 1.0:
                    vFxd_next = vFuncFxd_next(mNrm_next, z)
                    # Combine by adjustment probability
                    v_next = AdjustPrb * vAdj_next + (1.0 - AdjustPrb) * vFxd_next
                else:  # Don't bother evaluating if there's no chance that portfolio share is fixed
                    v_next = vAdj_next

                v_intermed = (S["PermShk"] * PermGroFac) ** (1.0 - CRRA) * v_next
                return v_intermed

            # Calculate intermediate value by taking expectations over income shocks
            v_intermed = expected(
                calc_v_intermed, IncShkDstn, args=(bNrmNext, ShareNext)
            )

            # Construct the "intermediate value function" for this period
            vNvrs_intermed = uFunc.inv(v_intermed)
            vNvrsFunc_intermed = BilinearInterp(vNvrs_intermed, bNrmGrid, ShareGrid)
            vFunc_intermed = ValueFuncCRRA(vNvrsFunc_intermed, CRRA)

            def calc_EndOfPrd_v(S, a, z):
                # Calculate future realizations of bank balances bNrm
                Rxs = S - Rfree
                Rport = Rfree + z * Rxs
                bNrm_next = Rport * a

                # Make an extended share_next of the same dimension as b_nrm so
                # that the function can be vectorized
                z_rep = z + np.zeros_like(bNrm_next)

                EndOfPrd_v = vFunc_intermed(bNrm_next, z_rep)
                return EndOfPrd_v

            # Calculate end-of-period value by taking expectations
            EndOfPrd_v = DiscFacEff * expected(
                calc_EndOfPrd_v, RiskyDstn, args=(aNrmNow, ShareNext)
            )
            EndOfPrd_vNvrs = uFunc.inv(EndOfPrd_v)

            # Now make an end-of-period value function over aNrm and Share
            EndOfPrd_vNvrsFunc = BilinearInterp(EndOfPrd_vNvrs, aNrmGrid, ShareGrid)
            EndOfPrd_vFunc = ValueFuncCRRA(EndOfPrd_vNvrsFunc, CRRA)
            # This will be used later to make the value function for this period

    # If the income shock distribution and risky return distribution are *NOT*
    # independent, then computation of end-of-period expectations are simpler in
    # code, but might take longer to execute
    else:
        # Make tiled arrays to calculate future realizations of mNrm and Share when integrating over IncShkDstn
        aNrmNow, ShareNext = np.meshgrid(aNrmGrid, ShareGrid, indexing="ij")

        # Define functions that are used internally to evaluate future realizations
        def calc_mNrm_next(S, a, z):
            """
            Calculate future realizations of market resources mNrm from the shock
            distribution S, normalized end-of-period assets a, and risky share z.
            """
            # Calculate future realizations of bank balances bNrm
            Rxs = S["Risky"] - Rfree
            Rport = Rfree + z * Rxs
            bNrm_next = Rport * a
            mNrm_next = bNrm_next / (S["PermShk"] * PermGroFac) + S["TranShk"]
            return mNrm_next

        def calc_EndOfPrd_dvdx(S, a, z):
            """
            Evaluate end-of-period marginal value of assets and risky share based
            on the shock distribution S, values of bend of period assets a, and
            risky share z.
            """
            mNrm_next = calc_mNrm_next(S, a, z)
            Rxs = S["Risky"] - Rfree
            Rport = Rfree + z * Rxs
            dvdmAdj_next = vPfuncAdj_next(mNrm_next)
            # No marginal value of Share if it's a free choice!
            dvdsAdj_next = np.zeros_like(mNrm_next)

            if AdjustPrb < 1.0:
                # Expand to the same dimensions as mNrm
                Share_next_expanded = z + np.zeros_like(mNrm_next)
                dvdmFxd_next = dvdmFuncFxd_next(mNrm_next, Share_next_expanded)
                dvdsFxd_next = dvdsFuncFxd_next(mNrm_next, Share_next_expanded)
                # Combine by adjustment probability
                dvdm_next = AdjustPrb * dvdmAdj_next + (1.0 - AdjustPrb) * dvdmFxd_next
                dvds_next = AdjustPrb * dvdsAdj_next + (1.0 - AdjustPrb) * dvdsFxd_next
            else:  # Don't bother evaluating if there's no chance that portfolio share is fixed
                dvdm_next = dvdmAdj_next
                dvds_next = dvdsAdj_next

            EndOfPrd_dvda = Rport * (S["PermShk"] * PermGroFac) ** (-CRRA) * dvdm_next
            EndOfPrd_dvds = (
                Rxs * a * (S["PermShk"] * PermGroFac) ** (-CRRA) * dvdm_next
                + (S["PermShk"] * PermGroFac) ** (1 - CRRA) * dvds_next
            )

            return EndOfPrd_dvda, EndOfPrd_dvds

        def calc_EndOfPrd_v(S, a, z):
            """
            Evaluate end-of-period value, based on the shock distribution S, values
            of bank balances bNrm, and values of the risky share z.
            """
            mNrm_next = calc_mNrm_next(S, a, z)
            vAdj_next = vFuncAdj_next(mNrm_next)

            if AdjustPrb < 1.0:
                # Expand to the same dimensions as mNrm
                Share_next_expanded = z + np.zeros_like(mNrm_next)
                vFxd_next = vFuncFxd_next(mNrm_next, Share_next_expanded)
                # Combine by adjustment probability
                v_next = AdjustPrb * vAdj_next + (1.0 - AdjustPrb) * vFxd_next
            else:  # Don't bother evaluating if there's no chance that portfolio share is fixed
                v_next = vAdj_next

            EndOfPrd_v = (S["PermShk"] * PermGroFac) ** (1.0 - CRRA) * v_next
            return EndOfPrd_v

        # Evaluate realizations of value and marginal value after asset returns are realized

        # Calculate end-of-period marginal value of assets and risky share by taking expectations
        EndOfPrd_dvda, EndOfPrd_dvds = DiscFacEff * expected(
            calc_EndOfPrd_dvdx, ShockDstn, args=(aNrmNow, ShareNext)
        )
        EndOfPrd_dvdaNvrs = uFunc.derinv(EndOfPrd_dvda)

        # Construct the end-of-period value function if requested
        if vFuncBool:
            # Calculate end-of-period value, its derivative, and their pseudo-inverse
            EndOfPrd_v = DiscFacEff * expected(
                calc_EndOfPrd_v, ShockDstn, args=(aNrmNow, ShareNext)
            )
            EndOfPrd_vNvrs = uFunc.inv(EndOfPrd_v)

            # value transformed through inverse utility
            EndOfPrd_vNvrsP = EndOfPrd_dvda * uFunc.derinv(EndOfPrd_v, order=(0, 1))

            # Construct the end-of-period value function
            EndOfPrd_vNvrsFunc_by_Share = []
            for j in range(ShareCount):
                EndOfPrd_vNvrsFunc_by_Share.append(
                    CubicInterp(
                        aNrmNow[:, j], EndOfPrd_vNvrs[:, j], EndOfPrd_vNvrsP[:, j]
                    )
                )
            EndOfPrd_vNvrsFunc = LinearInterpOnInterp1D(
                EndOfPrd_vNvrsFunc_by_Share, ShareGrid
            )
            EndOfPrd_vFunc = ValueFuncCRRA(EndOfPrd_vNvrsFunc, CRRA)

    # Find the optimal risky asset share either by choosing the best value among
    # the discrete grid choices, or by satisfying the FOC with equality (continuous)
    if DiscreteShareBool:
        # If we're restricted to discrete choices, then portfolio share is
        # the one with highest value for each aNrm gridpoint
        opt_idx = np.argmax(EndOfPrd_v, axis=1)
        ShareAdj_now = ShareGrid[opt_idx]

        # Take cNrm at that index as well... and that's it!
        cNrmAdj_now = EndOfPrd_dvdaNvrs[np.arange(aNrmCount), opt_idx]

    else:
        # Now find the optimal (continuous) risky share on [0,1] by solving the first
        # order condition EndOfPrd_dvds == 0.
        FOC_s = EndOfPrd_dvds  # Relabel for convenient typing

        # For each value of aNrm, find the value of Share such that FOC_s == 0
        crossing = np.logical_and(FOC_s[:, 1:] <= 0.0, FOC_s[:, :-1] >= 0.0)
        share_idx = np.argmax(crossing, axis=1)
        # This represents the index of the segment of the share grid where dvds flips
        # from positive to negative, indicating that there's a zero *on* the segment

        # Calculate the fractional distance between those share gridpoints where the
        # zero should be found, assuming a linear function; call it alpha
        a_idx = np.arange(aNrmCount)
        bot_s = ShareGrid[share_idx]
        top_s = ShareGrid[share_idx + 1]
        bot_f = FOC_s[a_idx, share_idx]
        top_f = FOC_s[a_idx, share_idx + 1]
        bot_c = EndOfPrd_dvdaNvrs[a_idx, share_idx]
        top_c = EndOfPrd_dvdaNvrs[a_idx, share_idx + 1]
        alpha = 1.0 - top_f / (top_f - bot_f)

        # Calculate the continuous optimal risky share and optimal consumption
        ShareAdj_now = (1.0 - alpha) * bot_s + alpha * top_s
        cNrmAdj_now = (1.0 - alpha) * bot_c + alpha * top_c

        # If agent wants to put more than 100% into risky asset, he is constrained.
        # Likewise if he wants to put less than 0% into risky asset, he is constrained.
        constrained_top = FOC_s[:, -1] > 0.0
        constrained_bot = FOC_s[:, 0] < 0.0

        # Apply those constraints to both risky share and consumption (but lower
        # constraint should never be relevant)
        ShareAdj_now[constrained_top] = 1.0
        ShareAdj_now[constrained_bot] = 0.0
        cNrmAdj_now[constrained_top] = EndOfPrd_dvdaNvrs[constrained_top, -1]
        cNrmAdj_now[constrained_bot] = EndOfPrd_dvdaNvrs[constrained_bot, 0]

    # When the natural borrowing constraint is *not* zero, then aNrm=0 is in the
    # grid, but there's no way to "optimize" the portfolio if a=0, and consumption
    # can't depend on the risky share if it doesn't meaningfully exist. Apply
    # a small fix to the bottom gridpoint (aNrm=0) when this happens.
    if not BoroCnstNat_iszero:
        ShareAdj_now[0] = 1.0
        cNrmAdj_now[0] = EndOfPrd_dvdaNvrs[0, -1]

    # Construct functions characterizing the solution for this period

    # Calculate the endogenous mNrm gridpoints when the agent adjusts his portfolio,
    # then construct the consumption function when the agent can adjust his share
    mNrmAdj_now = np.insert(aNrmGrid + cNrmAdj_now, 0, 0.0)
    cNrmAdj_now = np.insert(cNrmAdj_now, 0, 0.0)
    cFuncAdj_now = LinearInterp(mNrmAdj_now, cNrmAdj_now)

    # Construct the marginal value (of mNrm) function when the agent can adjust
    vPfuncAdj_now = MargValueFuncCRRA(cFuncAdj_now, CRRA)

    # Construct the consumption function when the agent *can't* adjust the risky
    # share, as well as the marginal value of Share function
    cFuncFxd_by_Share = []
    dvdsFuncFxd_by_Share = []
    for j in range(ShareCount):
        cNrmFxd_temp = np.insert(EndOfPrd_dvdaNvrs[:, j], 0, 0.0)
        mNrmFxd_temp = np.insert(aNrmGrid + cNrmFxd_temp[1:], 0, 0.0)
        dvdsFxd_temp = np.insert(EndOfPrd_dvds[:, j], 0, EndOfPrd_dvds[0, j])
        cFuncFxd_by_Share.append(LinearInterp(mNrmFxd_temp, cNrmFxd_temp))
        dvdsFuncFxd_by_Share.append(LinearInterp(mNrmFxd_temp, dvdsFxd_temp))
    cFuncFxd_now = LinearInterpOnInterp1D(cFuncFxd_by_Share, ShareGrid)
    dvdsFuncFxd_now = LinearInterpOnInterp1D(dvdsFuncFxd_by_Share, ShareGrid)

    # The share function when the agent can't adjust his portfolio is trivial
    ShareFuncFxd_now = IdentityFunction(i_dim=1, n_dims=2)

    # Construct the marginal value of mNrm function when the agent can't adjust his share
    dvdmFuncFxd_now = MargValueFuncCRRA(cFuncFxd_now, CRRA)

    # Construct the optimal risky share function when adjusting is possible.
    # The interpolation method depends on whether the choice is discrete or continuous.
    if DiscreteShareBool:
        # If the share choice is discrete, the "interpolated" share function acts
        # like a step function, with jumps at the midpoints of mNrm gridpoints.
        # Because an actual step function would break our (assumed continuous) linear
        # interpolator, there's a *tiny* region with extremely high slope.
        mNrmAdj_mid = (mNrmAdj_now[2:] + mNrmAdj_now[1:-1]) / 2
        mNrmAdj_plus = mNrmAdj_mid * (1.0 + 1e-12)
        mNrmAdj_comb = (np.transpose(np.vstack((mNrmAdj_mid, mNrmAdj_plus)))).flatten()
        mNrmAdj_comb = np.append(np.insert(mNrmAdj_comb, 0, 0.0), mNrmAdj_now[-1])
        Share_comb = (np.transpose(np.vstack((ShareAdj_now, ShareAdj_now)))).flatten()
        ShareFuncAdj_now = LinearInterp(mNrmAdj_comb, Share_comb)

    else:
        # If the share choice is continuous, just make an ordinary interpolating function
        if BoroCnstNat_iszero:
            Share_lower_bound = ShareLimit
        else:
            Share_lower_bound = 1.0
        ShareAdj_now = np.insert(ShareAdj_now, 0, Share_lower_bound)
        ShareFuncAdj_now = LinearInterp(mNrmAdj_now, ShareAdj_now, ShareLimit, 0.0)

    # This is a point at which (a,c,share) have consistent length. Take the
    # snapshot for storing the grid and values in the solution.
    save_points = {
        "a": deepcopy(aNrmGrid),
        "eop_dvda_adj": uFunc.der(cNrmAdj_now),
        "share_adj": deepcopy(ShareAdj_now),
        "share_grid": deepcopy(ShareGrid),
        "eop_dvda_fxd": uFunc.der(EndOfPrd_dvda),
        "eop_dvds_fxd": EndOfPrd_dvds,
    }

    # Add the value function if requested
    if vFuncBool:
        # Create the value functions for this period, defined over market resources
        # mNrm when agent can adjust his portfolio, and over market resources and
        # fixed share when agent can not adjust his portfolio.

        # Construct the value function when the agent can adjust his portfolio
        mNrm_temp = aXtraGrid  # Just use aXtraGrid as our grid of mNrm values
        cNrm_temp = cFuncAdj_now(mNrm_temp)
        aNrm_temp = np.maximum(mNrm_temp - cNrm_temp, 0.0)  # Fix tiny violations
        Share_temp = ShareFuncAdj_now(mNrm_temp)
        v_temp = uFunc(cNrm_temp) + EndOfPrd_vFunc(aNrm_temp, Share_temp)
        vNvrs_temp = uFunc.inv(v_temp)
        vNvrsP_temp = uFunc.der(cNrm_temp) * uFunc.inverse(v_temp, order=(0, 1))
        vNvrsFuncAdj = CubicInterp(
            np.insert(mNrm_temp, 0, 0.0),  # x_list
            np.insert(vNvrs_temp, 0, 0.0),  # f_list
            np.insert(vNvrsP_temp, 0, vNvrsP_temp[0]),  # dfdx_list
        )
        # Re-curve the pseudo-inverse value function
        vFuncAdj_now = ValueFuncCRRA(vNvrsFuncAdj, CRRA)

        # Construct the value function when the agent *can't* adjust his portfolio
        mNrm_temp, Share_temp = np.meshgrid(aXtraGrid, ShareGrid)
        cNrm_temp = cFuncFxd_now(mNrm_temp, Share_temp)
        aNrm_temp = mNrm_temp - cNrm_temp
        v_temp = uFunc(cNrm_temp) + EndOfPrd_vFunc(aNrm_temp, Share_temp)
        vNvrs_temp = uFunc.inv(v_temp)
        vNvrsP_temp = uFunc.der(cNrm_temp) * uFunc.inverse(v_temp, order=(0, 1))
        vNvrsFuncFxd_by_Share = []
        for j in range(ShareCount):
            vNvrsFuncFxd_by_Share.append(
                CubicInterp(
                    np.insert(mNrm_temp[:, 0], 0, 0.0),  # x_list
                    np.insert(vNvrs_temp[:, j], 0, 0.0),  # f_list
                    np.insert(vNvrsP_temp[:, j], 0, vNvrsP_temp[j, 0]),  # dfdx_list
                )
            )
        vNvrsFuncFxd = LinearInterpOnInterp1D(vNvrsFuncFxd_by_Share, ShareGrid)
        vFuncFxd_now = ValueFuncCRRA(vNvrsFuncFxd, CRRA)

    else:  # If vFuncBool is False, fill in dummy values
        vFuncAdj_now = NullFunc()
        vFuncFxd_now = NullFunc()

    # Package and return the solution
    solution_now = PortfolioSolution(
        cFuncAdj=cFuncAdj_now,
        ShareFuncAdj=ShareFuncAdj_now,
        vPfuncAdj=vPfuncAdj_now,
        vFuncAdj=vFuncAdj_now,
        cFuncFxd=cFuncFxd_now,
        ShareFuncFxd=ShareFuncFxd_now,
        dvdmFuncFxd=dvdmFuncFxd_now,
        dvdsFuncFxd=dvdsFuncFxd_now,
        vFuncFxd=vFuncFxd_now,
        AdjPrb=AdjustPrb,
        # WHAT IS THIS STUFF FOR??
        aGrid=save_points["a"],
        Share_adj=save_points["share_adj"],
        EndOfPrddvda_adj=save_points["eop_dvda_adj"],
        ShareGrid=save_points["share_grid"],
        EndOfPrddvda_fxd=save_points["eop_dvda_fxd"],
        EndOfPrddvds_fxd=save_points["eop_dvds_fxd"],
    )
    solution_now.hNrm = hNrmNow
    solution_now.MPCmin = MPCminNow
    return solution_now


# Make a dictionary to specify a portfolio choice consumer type
init_portfolio = init_idiosyncratic_shocks.copy()
init_portfolio["RiskyAvg"] = 1.08  # Average return of the risky asset
init_portfolio["RiskyStd"] = 0.20  # Standard deviation of (log) risky returns
# Number of integration nodes to use in approximation of risky returns
init_portfolio["RiskyCount"] = 5
# Number of discrete points in the risky share approximation
init_portfolio["ShareCount"] = 25
# Probability that the agent can adjust their risky portfolio share each period
init_portfolio["AdjustPrb"] = 1.0
# Flag for whether to optimize risky share on a discrete grid only
init_portfolio["DiscreteShareBool"] = False

# Adjust some of the existing parameters in the dictionary
init_portfolio["aXtraMax"] = 100  # Make the grid of assets go much higher...
init_portfolio["aXtraCount"] = 200  # ...and include many more gridpoints...
# ...which aren't so clustered at the bottom
init_portfolio["aXtraNestFac"] = 1
# Artificial borrowing constraint must be turned on
init_portfolio["BoroCnstArt"] = 0.0
# Results are more interesting with higher risk aversion
init_portfolio["CRRA"] = 5.0
init_portfolio["DiscFac"] = 0.90  # And also lower patience
