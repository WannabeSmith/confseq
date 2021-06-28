import numpy as np
import math
import matplotlib.pyplot as plt
from time import time
from scipy.optimize import minimize, newton, root
import multiprocess
from copy import copy, deepcopy
from logging import info, warnings

from .predmix import lambda_predmix_eb


def betting_mart(
    x,
    m,
    alpha=0.05,
    lambdas_fn_positive=None,
    lambdas_fn_negative=None,
    N=None,
    convex_comb=False,
    theta=1 / 2,
    trunc_scale=1 / 2,
    m_trunc=True,
):
    """
    Betting martingale for a given sequence
    of data and a null mean value.

    Parameters
    ----------
    x, array-like
        The vector of observations between 0 and 1.

    m, real
        Null value for the mean of x

    alpha, real
        Significance level between 0 and 1.

    lambdas_fn_postive, bivariate function or None
        Function of `x` and `m` which generates an array-like
        of bets with the same length as `x`.

    lambdas_fn_negative=None, bivariate function or None
        Same as above but for the negative capital process.
        This will be set to lambdas_fn_positive if
        left as None.
    
    N, positive integer or None
        Population size if sampling WoR

    convex_comb, boolean
        Should a convex combination of martingales be taken?
        If True, the process will be theta*pcp + (1-theta)*ncp,
        and if False, it will be max(theta*pcp, (1-theta)*ncp) where
        pcp and ncp are the positive and negative capital processes,
        respectively.

    theta, [0, 1]-valued real
        Positive/negative capital process weight as
        defined in `convex_comb`

    trunc_scale, (0, 1]-valued real
        The factor by which to multiply the truncation defined
        in `m_trunc`. Leaving this as 1 will perform no
        additional truncation.

    m_trunc, boolean
        Should truncation be used based on m? If True, then truncation
        will be given by trunc_scale * 1/m or trunc_scale * 1/(1-m)
        depending on the capital process. If False, then truncation
        will be given by trunc_scale.


    Returns
    -------
    mart, array-like
        The martingale that results from the observed x
    """

    if lambdas_fn_positive is None:
        lambdas_fn_positive = lambda x, m: lambda_predmix_eb(x, alpha=alpha)

    if lambdas_fn_negative is None:
        lambdas_fn_negative = lambdas_fn_positive

    if N is not None:
        t = np.arange(1, len(x) + 1)
        S_t = np.cumsum(x)
        S_tminus1 = np.append(0, S_t[0 : (len(x) - 1)])
        mu_t = (N * m - S_tminus1) / (N - (t - 1))
    else:
        mu_t = np.repeat(m, len(x))

    lambdas_positive = lambdas_fn_positive(x, m)
    lambdas_negative = lambdas_fn_negative(x, m)

    # if we want to truncate with m
    if m_trunc:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            upper_trunc = trunc_scale / mu_t
            lower_trunc = trunc_scale / (1 - mu_t)

        if any(upper_trunc == math.inf):
            info("Truncating at 1000 instead of infinity")
            upper_trunc[upper_trunc == math.inf] = 1000
        if any(lower_trunc == math.inf):
            info("Truncating at -1000 instead of -infinity")
            lower_trunc[lower_trunc == math.inf] = 1000
    else:
        upper_trunc = trunc_scale
        lower_trunc = trunc_scale

    # perform truncation
    lambdas_positive = np.maximum(-lower_trunc, lambdas_positive)
    lambdas_positive = np.minimum(upper_trunc, lambdas_positive)

    lambdas_negative = np.maximum(-upper_trunc, lambdas_negative)
    lambdas_negative = np.minimum(lower_trunc, lambdas_negative)

    capital_process_positive = np.cumprod(1 + lambdas_positive * (x - mu_t))
    capital_process_negative = np.cumprod(1 - lambdas_negative * (x - mu_t))

    if theta == 1:
        capital_process = theta * capital_process_positive
    elif theta == 0:
        capital_process = (1 - theta) * capital_process_negative
    else:
        if convex_comb:
            capital_process = (
                theta * capital_process_positive
                + (1 - theta) * capital_process_negative
            )
        else:
            capital_process = np.maximum(
                theta * capital_process_positive, (1 - theta) * capital_process_negative
            )

    capital_process[mu_t <= 0] = math.inf
    capital_process[mu_t >= 1] = math.inf
    if any(capital_process < 0):
        assert all(capital_process >= 0)

    if any(np.isnan(capital_process)):
        warnings.warn("Martingale has nans")
        where = np.where(np.isnan(capital_process))[0]

        assert not any(np.isnan(capital_process))

    return capital_process


def betting_cs(
    x,
    lambdas_fns_positive=None,
    lambdas_fns_negative=None,
    alpha=0.05,
    N=None,
    breaks=1000,
    running_intersection=False,
    parallel=False,
    convex_comb=False,
    theta=1 / 2,
    trunc_scale=1 / 2,
    m_trunc=True,
):
    """
    Confidence sequence for the mean using the Betting
    empirical Bernstein martingale.

    Parameters
    ----------
    x, array-like
        The vector of observations between 0 and 1.

    m, real
        Null value for the mean of x

    alpha, real
        Significance level between 0 and 1.

    lambdas_fn_postive, bivariate function or None
        Function of `x` and `m` which generates an array-like
        of bets with the same length as `x`.

    lambdas_fn_negative=None, bivariate function or None
        Same as above but for the negative capital process.
        This will be set to lambdas_fn_positive if
        left as None.
    
    N, positive integer or None
        Population size if sampling WoR

    breaks, positive integer
        Number of breaks in the grid for constructing the confidence sequence
    
    running_intersection, boolean
        Should the running intersection be taken?

    parallel, boolean
        Should computation be parallelized?

    convex_comb, boolean
        Should a convex combination of martingales be taken?
        If True, the process will be theta*pcp + (1-theta)*ncp,
        and if False, it will be max(theta*pcp, (1-theta)*ncp) where
        pcp and ncp are the positive and negative capital processes,
        respectively.

    theta, [0, 1]-valued real
        Positive/negative capital process weight as
        defined in `convex_comb`

    trunc_scale, (0, 1]-valued real
        The factor by which to multiply the truncation defined
        in `m_trunc`. Leaving this as 1 will perform no
        additional truncation.

    m_trunc, boolean
        Should truncation be used based on m? If True, then truncation
        will be given by trunc_scale * 1/m or trunc_scale * 1/(1-m)
        depending on the capital process. If False, then truncation
        will be given by trunc_scale.


    Returns
    -------
    l, array-like
        Lower confidence sequence for the mean
    u, array-like
        Upper confidence sequence for the mean
    """
    if lambdas_fns_negative is None:
        lambdas_fns_negative = lambdas_fns_positive

    if np.shape(lambdas_fns_positive) == ():
        lambdas_fns_positive = [lambdas_fns_positive]
    if np.shape(lambdas_fns_negative) == ():
        lambdas_fns_negative = [lambdas_fns_negative]

    assert len(lambdas_fns_positive) == len(lambdas_fns_negative)

    mart_fn = lambda x, m: diversified_betting_mart(
        x,
        m,
        alpha=alpha,
        lambdas_fns_positive=lambdas_fns_positive,
        lambdas_fns_negative=lambdas_fns_negative,
        N=N,
        theta=theta,
        convex_comb=convex_comb,
        trunc_scale=trunc_scale,
        m_trunc=m_trunc,
    )

    l, u = cs_from_martingale(
        x,
        mart_fn,
        breaks=breaks,
        alpha=alpha,
        N=N,
        parallel=parallel,
        running_intersection=running_intersection,
    )

    return l, u


def diversified_betting_mart(
    x,
    m,
    lambdas_fns_positive,
    lambdas_fns_negative=None,
    lambdas_weights=None,
    alpha=None,
    N=None,
    convex_comb=False,
    theta=1 / 2,
    trunc_scale=1 / 2,
    m_trunc=True,
):
    mart = np.zeros(len(x))

    # Number of betting strategies to use
    K = len(lambdas_fns_positive)

    if lambdas_weights is None:
        lambdas_weights = np.repeat(1 / K, K)

    if lambdas_fns_negative is None:
        lambdas_fns_negative = lambdas_fns_positive

    assert len(lambdas_fns_positive) == len(lambdas_fns_negative)

    for k in range(K):
        lambdas_fn_positive = lambdas_fns_positive[k]
        lambdas_fn_negative = lambdas_fns_negative[k]
        mart = mart + lambdas_weights[k] * betting_mart(
            x,
            m,
            alpha=alpha,
            lambdas_fn_positive=lambdas_fn_positive,
            lambdas_fn_negative=lambdas_fn_negative,
            N=N,
            theta=theta,
            convex_comb=convex_comb,
            trunc_scale=trunc_scale,
            m_trunc=m_trunc,
        )
    return mart


def cs_from_martingale(
    x,
    mart_fn,
    breaks=1000,
    alpha=0.05,
    N=None,
    running_intersection=False,
    parallel=False,
):
    """
    Given a test supermartingale, produce a confidence sequence for
    any parameter using the grid method, assuming the parameter is
    in [0, 1]

    Parameters
    ----------
    x, array-like
        The vector of observations between 0 and 1.

    mart_fn, bivariate function
        A function which takes data `x` and a candidate mean `m`
        and outputs a (super)martingale.
    
    breaks, positive integer
        Number of breaks in the grid for constructing the confidence sequence

    alpha, real
        Significance level between 0 and 1.

    N, positive integer or None
        Population size if sampling WoR

    running_intersection, boolean
        Should the running intersection be taken?

    parallel, boolean
        Should computation be parallelized?

    Returns
    -------
    l, array-like
        Lower confidence sequence for the parameter
    u, array-like
        Upper confidence sequence for the parameter
    """
    possible_m = np.arange(0, 1 + 1 / breaks, step=1 / breaks)
    confseq_mtx = np.zeros((len(possible_m), len(x)))

    if parallel:
        n_cores = multiprocess.cpu_count()
        info("Using " + str(n_cores) + " cores")
        with multiprocess.Pool(n_cores) as p:
            result = p.map(lambda m: mart_fn(x, m), possible_m)
            confseq_mtx = np.vstack(result) <= 1 / alpha
    else:
        for i in np.arange(0, len(possible_m)):
            m = possible_m[i]
            confseq_mtx[i, :] = mart_fn(x, m) <= 1 / alpha

    l = np.zeros(len(x))
    u = np.ones(len(x))

    for j in np.arange(0, len(x)):
        where_in_cs = np.where(confseq_mtx[:, j])
        if len(where_in_cs[0]) == 0:
            l[j] = np.nan
            u[j] = np.nan
        else:
            l[j] = possible_m[where_in_cs[0][0]]
            u[j] = possible_m[where_in_cs[0][-1]]
    l = np.maximum(0, l - 1 / breaks)
    u = np.minimum(1, u + 1 / breaks)

    if N is not None:
        logical_l, logical_u = logical_cs(x, N)

        l = np.maximum(l, logical_l)
        u = np.minimum(u, logical_u)

    if running_intersection:
        l = np.maximum.accumulate(l)
        u = np.minimum.accumulate(u)

    return l, u


def hedged_cs():
    # TODO: just instantiate betting_cs with hedged parameters.
    pass


def dKelly_cs():
    # TODO: just instantiate betting_cs with dKelly parameters.
    pass


# def betting_cs_hedged(
#     x,
#     alpha=0.05,
#     theta=1 / 2,
#     breaks=1000,
#     running_intersection=False,
#     trunc_scale=1 / 2,
# ):
#     n = len(x)

#     lambdas = lambda_predmix_eb(
#         x, truncation=math.inf, alpha=alpha / 2, prior_mean=1 / 2, prior_variance=1 / 4
#     )
#     possible_m = np.arange(0, 1 + 1 / breaks, step=1 / breaks)
#     x_mtx = np.tile(x, (breaks + 1, 1))
#     m_mtx = np.tile(possible_m, (n, 1)).transpose()

#     lambdas_mtx_positive = np.tile(lambdas, (breaks + 1, 1))
#     lambdas_mtx_negative = copy.deepcopy(lambdas_mtx_positive)
#     lambdas_mtx_positive = np.minimum(lambdas_mtx_positive, trunc_scale / m_mtx)
#     lambdas_mtx_negative = np.minimum(lambdas_mtx_negative, trunc_scale / (1 - m_mtx))
#     # capital matrix, positive part
#     cap_mtx_pos = np.cumprod(1 + lambdas_mtx_positive * (x_mtx - m_mtx), axis=1)
#     # capital matrix, negative part
#     cap_mtx_neg = np.cumprod(1 - lambdas_mtx_negative * (x_mtx - m_mtx), axis=1)
#     capital_mtx = theta * cap_mtx_pos + (1 - theta) * cap_mtx_neg

#     lu = np.array(
#         [
#             (possible_m[no_reject[0]], possible_m[no_reject[-1]])
#             for no_reject in [
#                 np.where(capital_mtx[:, i] < 1 / alpha)[0] for i in range(n)
#             ]
#         ]
#     ).transpose()
#     l, u = lu[0, :], lu[1, :]

#     # Take superset since we're gridding up [0, 1]
#     l = l - 1 / breaks
#     u = u + 1 / breaks

#     # intersect with [0, 1]
#     l = np.maximum(l, 0)
#     u = np.minimum(u, 1)

#     if running_intersection:
#         l = np.maximum.accumulate(l)
#         u = np.minimum.accumulate(u)

#     return l, u


def logical_cs(x, N):
    """
    The 1-dimensional logical confidence sequence for sampling without
    replacement. This is essentially the CS that would be
    known regardless of the underlying martingale being used.
    Specifically, if the cumulative sum at time t, S_t is equal to
    5 and N is 10, then the true mean cannot be any less than 0.5, assuming
    all observations are between 0 and 1.

    Parameters
    ----------
    x, array-like of reals between 0 and 1
        The observed bounded random variables.
    N, integer
        The size of the finite population

    Returns
    -------
    l, array-like
        Lower logical confidence sequence for the parameter
    u, array-like
        Upper logical confidence sequence for the parameter
    """
    t = np.arange(1, len(x) + 1)

    S_t = np.cumsum(x)

    l = S_t / N
    u = 1 - (t - S_t) / N

    return l, u


def mu_t(x, m, N):
    t = np.arange(1, len(x) + 1)
    S_t = np.cumsum(x)
    S_tminus1 = np.append(0, S_t[0 : (len(x) - 1)])
    mu_t = (N * m - S_tminus1) / (N - (t - 1))

    return mu_t


def betting_ci(
    x,
    alpha=0.05,
    lambdas_fns_positive=None,
    lambdas_fns_negative=None,
    N=None,
    breaks=1000,
    running_intersection=True,
    parallel=False,
    convex_comb=False,
    theta=1/2,
    trunc_scale=1,
    m_trunc=False,
):
    """
    Fixed-time, betting-based confidence interval

    Parameters
    ----------
    x, array-like
        The vector of observations between 0 and 1.

    alpha, real
        Significance level between 0 and 1.

    lambdas_fn_postive, bivariate function or None
        Function of `x` and `m` which generates an array-like
        of bets with the same length as `x`.

    lambdas_fn_negative=None, bivariate function or None
        Same as above but for the negative capital process.
        This will be set to lambdas_fn_positive if
        left as None.
    
    N, positive integer or None
        Population size if sampling WoR

    breaks, positive integer
        Number of breaks in the grid for constructing the confidence sequence
    
    running_intersection, boolean
        Should the running intersection be taken?

    parallel, boolean
        Should computation be parallelized?

    convex_comb, boolean
        Should a convex combination of martingales be taken?
        If True, the process will be theta*pcp + (1-theta)*ncp,
        and if False, it will be max(theta*pcp, (1-theta)*ncp) where
        pcp and ncp are the positive and negative capital processes,
        respectively.

    theta, [0, 1]-valued real
        Positive/negative capital process weight as
        defined in `convex_comb`

    trunc_scale, (0, 1]-valued real
        The factor by which to multiply the truncation defined
        in `m_trunc`. Leaving this as 1 will perform no
        additional truncation.

    m_trunc, boolean
        Should truncation be used based on m? If True, then truncation
        will be given by trunc_scale * 1/m or trunc_scale * 1/(1-m)
        depending on the capital process. If False, then truncation
        will be given by trunc_scale.

    Returns
    -------
    l, real
        Lower confidence bound
    u, real
        Upper confidence bound
    """
    x = np.array(x)
    n = len(x)

    l, u = betting_cs(
        x,
        alpha=alpha,
        breaks=breaks,
        lambdas_fns_positive=lambdas_fns_positive,
        lambdas_fns_negative=lambdas_fns_negative,
        N=N,
        running_intersection=running_intersection,
        parallel=parallel,
        convex_comb=convex_comb,
        theta=theta,
        trunc_scale=trunc_scale,
        m_trunc=m_trunc,
    )

    return l[-1], u[-1]


def get_ci_seq(x, ci_fn, times, parallel=False):
    """
    Get sequence of confidence intervals
    
    Parameters
    ----------
    x, array-like
        The vector of observations between 0 and 1.

    ci_fn, univariate function
        A function which takes an array-like of bounded numbers `x`
        and outputs a tuple `(l, u)` of lower and upper confidence
        intervals. Note that `l` and `u` are scalars (not vectors).
    
    times, array-like of positive integers
        Times at which to compute the confidence interval.
        
    parallel, boolean
        Should this function be parallelized?
        
    Returns
    -------
    l, array-like of [0, 1]-valued reals
        Lower confidence intervals

    u, array-like of [0, 1]-valued reals
        Upper confidence intervals
    """
    x = np.array(x)

    l = np.repeat(0.0, len(times))
    u = np.repeat(1.0, len(times))

    if parallel:
        n_cores = multiprocess.cpu_count()
        print("Using " + str(n_cores) + " cores")
        with multiprocess.Pool(n_cores) as p:
            result = np.array(p.map(lambda time: ci_fn(x[0:time]), times))
        l, u = result[:, 0], result[:, 1]
    else:
        for i in np.arange(0, len(times)):
            time = times[i]
            x_t = x[0:time]
            l[i], u[i] = ci_fn(x_t)

    return l, u


def betting_ci_seq(
    x,
    alpha,
    times,
    lambdas_fns_positive=None,
    lambdas_fns_negative=None,
    N=None,
    breaks=1000,
    running_intersection=True,
    parallel=False,
    convex_comb=False,
    theta=1/2,
    trunc_scale=0.9,
    m_trunc=True,
):
    """
    Sequence of fixed-time, betting martingale-based confidence intervals

    Parameters
    ----------
    x, array-like
        The vector of observations between 0 and 1.

    alpha, (0, 1)-bounded real
        Significance level between 0 and 1.

    lambdas_fn_postive, bivariate function or None
        Function of `x` and `m` which generates an array-like
        of bets with the same length as `x`.

    lambdas_fn_negative=None, bivariate function or None
        Same as above but for the negative capital process.
        This will be set to lambdas_fn_positive if
        left as None.
    
    N, positive integer or None
        Population size if sampling WoR

    breaks, positive integer
        Number of breaks in the grid for constructing the confidence sequence
    
    running_intersection, boolean
        Should the running intersection be taken?

    parallel, boolean
        Should computation be parallelized?

    convex_comb, boolean
        Should a convex combination of martingales be taken?
        If True, the process will be theta*pcp + (1-theta)*ncp,
        and if False, it will be max(theta*pcp, (1-theta)*ncp) where
        pcp and ncp are the positive and negative capital processes,
        respectively.

    theta, [0, 1]-valued real
        Positive/negative capital process weight as
        defined in `convex_comb`

    trunc_scale, (0, 1]-valued real
        The factor by which to multiply the truncation defined
        in `m_trunc`. Leaving this as 1 will perform no
        additional truncation.

    m_trunc, boolean
        Should truncation be used based on m? If True, then truncation
        will be given by trunc_scale * 1/m or trunc_scale * 1/(1-m)
        depending on the capital process. If False, then truncation
        will be given by trunc_scale.

    Returns
    -------
    l, array-like of reals
        Lower confidence intervals

    u, array-like of reals
        Upper confidence intervals
    """

    def ci_fn(x):
        return betting_ci(
            x,
            alpha=alpha,
            breaks=breaks,
            lambdas_fns_positive=lambdas_fns_positive,
            lambdas_fns_negative=lambdas_fns_negative,
            N=N,
            running_intersection=running_intersection,
            convex_comb=convex_comb,
            theta=theta,
            trunc_scale=trunc_scale,
            m_trunc=m_trunc,
        )

    return get_ci_seq(x, ci_fn, times=times, parallel=parallel)
