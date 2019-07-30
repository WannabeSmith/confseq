#ifndef CONFIDENCESEQUENCES_UNIFORM_BOUNDARIES_H_
#define CONFIDENCESEQUENCES_UNIFORM_BOUNDARIES_H_

#include <boost/math/distributions/normal.hpp>
#include <boost/math/special_functions/beta.hpp>
#include <boost/math/special_functions/gamma.hpp>
#include <boost/math/special_functions/zeta.hpp>
#include <boost/math/tools/roots.hpp>

namespace confseq {

//////////////////////////////////////////////////////////////////////
// Simplified interface
//////////////////////////////////////////////////////////////////////

double normal_log_mixture(const double s, const double v, const double v_opt,
                          const double alpha_opt=0.05,
                          const bool is_one_sided=true);

double normal_mixture_bound(
    const double v, const double alpha, const double v_opt,
    const double alpha_opt=0.05, const bool is_one_sided=true);

double gamma_exponential_log_mixture(
    const double s, const double v, const double v_opt,
    const double c, const double alpha_opt=0.05);

double gamma_exponential_mixture_bound(
    const double v, const double alpha, const double v_opt,
    const double c, const double alpha_opt=0.05);

double gamma_poisson_log_mixture(
    const double s, const double v, const double v_opt, const double c,
    const double alpha_opt=0.05);

double gamma_poisson_mixture_bound(
    const double v, const double alpha, const double v_opt, const double c,
    const double alpha_opt=0.05);

double beta_binomial_log_mixture(
    const double s, const double v, const double v_opt, const double g,
    const double h, const double alpha_opt=0.05,
    const bool is_one_sided=true);

double beta_binomial_mixture_bound(
    const double v, const double alpha, const double v_opt, const double g,
    const double h, const double alpha_opt=0.05,
    const bool is_one_sided=true);

double poly_stitching_bound(const double v, const double alpha,
                            const double v_min, const double c=0,
                            const double s=1.4, const double eta=2);

//////////////////////////////////////////////////////////////////////
// Object-oriented interface
//////////////////////////////////////////////////////////////////////

// (v, alpha) -> boundary value
using UniformBoundary = std::function<double(const double, const double)>;

class MixtureSupermartingale {
public:
  virtual ~MixtureSupermartingale() {}
  virtual double log_superMG(const double s, const double v) const = 0;
  virtual double s_upper_bound(const double v) const = 0;
  virtual double bound(const double v, const double log_threshold) const = 0;
};

double find_mixture_bound(const MixtureSupermartingale& mixture_superMG,
                          const double v, const double log_threshold);

class TwoSidedNormalMixture : public MixtureSupermartingale {
 public:
  TwoSidedNormalMixture(double v_opt, double alpha_opt)
    : rho_(best_rho(v_opt, alpha_opt)) {
    assert(v_opt > 0);
  }

  double log_superMG(const double s, const double v) const override;
  double s_upper_bound(const double /*v*/) const override {
    return std::numeric_limits<double>::infinity();
  }
  double bound(const double v, const double log_threshold) const override;
  static double best_rho(double v, double alpha);

 private:
  const double rho_;
};

class OneSidedNormalMixture : public MixtureSupermartingale {
 public:
  OneSidedNormalMixture(double v_opt, double alpha_opt)
    : rho_(best_rho(v_opt, alpha_opt)) {
    assert(v_opt > 0);
  }

  double log_superMG(const double s, const double v) const override;
  double s_upper_bound(const double /*v*/) const override {
    return std::numeric_limits<double>::infinity();
  }
  double bound(const double v, const double log_threshold) const override {
    return find_mixture_bound(*this, v, log_threshold);
  }
  static double best_rho(double v, double alpha);

 private:
  const double rho_;
};

class GammaExponentialMixture : public MixtureSupermartingale {
 public:
  GammaExponentialMixture(double v_opt, double alpha_opt, double c)
      : rho_(OneSidedNormalMixture::best_rho(v_opt, alpha_opt)),
        c_(c), leading_constant_(get_leading_constant(rho_, c_)) {}

  double log_superMG(const double s, const double v) const override;
  double s_upper_bound(const double /*v*/) const override {
    return std::numeric_limits<double>::infinity();
  }
  double bound(const double v, const double log_threshold) const override {
    return find_mixture_bound(*this, v, log_threshold);
  }

 private:
  static double get_leading_constant(double rho, double c);

  const double rho_;
  const double c_;
  const double leading_constant_;
};

class GammaPoissonMixture : public MixtureSupermartingale {
 public:
  GammaPoissonMixture(double v_opt, double alpha_opt, double c)
      : rho_(OneSidedNormalMixture::best_rho(v_opt, alpha_opt)),
        c_(c), leading_constant_(get_leading_constant(rho_, c_)) {}

  double log_superMG(const double s, const double v) const override;
  double s_upper_bound(const double /*v*/) const override {
    return std::numeric_limits<double>::infinity();
  }
  double bound(const double v, const double log_threshold) const override {
    return find_mixture_bound(*this, v, log_threshold);
  }

 private:
  static double get_leading_constant(double rho, double c);

  const double rho_;
  const double c_;
  const double leading_constant_;
};

class BetaBinomialMixture : public MixtureSupermartingale {
 public:

  BetaBinomialMixture(double v_opt, double alpha_opt, double g, double h,
                      bool is_one_sided)
      : r_((is_one_sided? OneSidedNormalMixture::best_rho(v_opt, alpha_opt)
                        : TwoSidedNormalMixture::best_rho(v_opt, alpha_opt))
           - g * h),
        g_(g), h_(h), is_one_sided_(is_one_sided) {
    assert(g > 0);
    assert(h > 0);
    assert(r_ > 0);
  }

  double log_superMG(const double s, const double v) const override;
  double s_upper_bound(const double v) const override;
  double bound(const double v, const double log_threshold) const override {
    return find_mixture_bound(*this, v, log_threshold);
  }

 private:
  const double r_;
  const double g_;
  const double h_;
  const bool is_one_sided_;
};

class PolyStitchingBound {
 public:
  PolyStitchingBound(double v_min, double c, double s, double eta)
    : v_min_(v_min), c_(c), s_(s), eta_(eta),
      k1_((pow(eta, .25) + pow(eta, -.25)) / sqrt(2)),
      k2_((sqrt(eta) + 1) / 2),
      A_(log(boost::math::zeta(s) / pow(log(eta), s))) {
    assert(v_min > 0);
  }

  double operator()(const double v, const double alpha) const;

  const double v_min_;
  const double c_;
  const double s_;
  const double eta_;
  const double k1_;
  const double k2_;
  const double A_;
};

class MixtureBoundary {
public:
  MixtureBoundary(std::unique_ptr<MixtureSupermartingale>&& mixture_superMG)
      : mixture_superMG_(std::move(mixture_superMG)) {}

  double operator()(const double v, const double alpha) const {
    return mixture_superMG_->bound(v, log(1 / alpha));
  }

private:
  std::unique_ptr<MixtureSupermartingale> mixture_superMG_;
};

//////////////////////////////////////////////////////////////////////
// Implementation
//////////////////////////////////////////////////////////////////////

double find_s_upper_bound(const MixtureSupermartingale& mixture_superMG,
                          const double v, const double log_threshold) {
  double trial_upper_bound = v;
  for (int i = 0; i < 50; i++) {
    if (mixture_superMG.log_superMG(trial_upper_bound, v) > log_threshold) {
      return trial_upper_bound;
    }
    trial_upper_bound *= 2;
  }
  return trial_upper_bound; // bisect() will indicate the error
}

double find_mixture_bound(const MixtureSupermartingale& mixture_superMG,
                          const double v, const double log_threshold) {
  auto root_fn = [&mixture_superMG, v, log_threshold](const double s) {
    return mixture_superMG.log_superMG(s, v) - log_threshold;
  };
  double s_upper_bound = mixture_superMG.s_upper_bound(v);
  if (s_upper_bound == std::numeric_limits<double>::infinity()) {
    s_upper_bound = find_s_upper_bound(mixture_superMG, v, log_threshold);
  }
  // TODO: deal with infinite upper bound
  auto result = boost::math::tools::bisect(
      root_fn, 0.0, s_upper_bound,
      boost::math::tools::eps_tolerance<double>(40));
  return (result.first + result.second) / 2;
}

double TwoSidedNormalMixture::log_superMG(const double s, const double v)
    const {
  return (1 / 2.0) * log(rho_ / (v + rho_)) + s * s / (2 * (v + rho_));
}

double TwoSidedNormalMixture::bound(const double v, const double log_threshold)
    const {
  return sqrt((v + rho_) * (log(1 + v / rho_) + 2 * log_threshold));
}

double TwoSidedNormalMixture::best_rho(double v, double alpha) {
  assert(v > 0);
  assert(0 < alpha && alpha < 1);
  return v / (2 * log(1 / alpha) + log(1 + 2 * log(1 / alpha)));
}

double OneSidedNormalMixture::log_superMG(const double s, const double v)
    const {
  boost::math::normal_distribution<double> normal;
  return (1 / 2.0) * log(4 * rho_ / (v + rho_)) + s * s / (2 * (v + rho_))
      + log(boost::math::cdf(normal, s / sqrt(v + rho_)));
}

double OneSidedNormalMixture::best_rho(double v, double alpha) {
  return TwoSidedNormalMixture::best_rho(v, 2 * alpha);
}

double GammaExponentialMixture::get_leading_constant(double rho, double c) {
  const double rho_c_sq = rho / (c * c);
  return rho_c_sq * log(rho_c_sq)
      - boost::math::lgamma(rho_c_sq)
      - log(boost::math::gamma_p(rho_c_sq, rho_c_sq));
}

double GammaExponentialMixture::log_superMG(const double s, const double v)
    const {
  const double c_sq = c_ * c_;
  const double cs_v_csq = (c_ * s + v) / c_sq;
  const double v_rho_csq = (v + rho_) / c_sq;
  return leading_constant_
      + boost::math::lgamma(v_rho_csq)
      + log(boost::math::gamma_p(v_rho_csq, cs_v_csq + rho_ / c_sq))
      - v_rho_csq * log(cs_v_csq + rho_ / c_sq)
      + cs_v_csq;
}

double GammaPoissonMixture::get_leading_constant(double rho, double c) {
  const double rho_c_sq = rho / (c * c);
  return rho_c_sq * log(rho_c_sq)
      - boost::math::lgamma(rho_c_sq)
      - log(boost::math::gamma_q(rho_c_sq, rho_c_sq));
}

double GammaPoissonMixture::log_superMG(const double s, const double v)
    const {
  const double c_sq = c_ * c_;
  const double v_rho_csq = (v + rho_) / c_sq;
  const double cs_v_rho_csq = s / c_ + v_rho_csq;
  return leading_constant_
      + boost::math::lgamma(cs_v_rho_csq)
      + log(boost::math::gamma_q(cs_v_rho_csq, v_rho_csq))
      - cs_v_rho_csq * log(v_rho_csq)
      + v / c_sq;
}

double log_beta(const double a, const double b) {
  return boost::math::lgamma(a) + boost::math::lgamma(b)
      - boost::math::lgamma(a + b);
}

double log_incomplete_beta(const double a, const double b, const double x) {
  if (x == 1) {
    return log_beta(a, b);
  } else {
    return log(boost::math::ibeta(a, b, x)) + log_beta(a, b);
  }
}

double BetaBinomialMixture::log_superMG(const double s, const double v)
    const {
  const double x = is_one_sided_ ? h_ / (g_ + h_) : 1;
  return
      v / (g_ * h_) * log(g_ + h_)
      - ((v + h_ * s) / (h_ * (g_ + h_))) * log(g_)
      - ((v - g_ * s) / (g_ * (g_ + h_))) * log(h_)
      + log_incomplete_beta((r_ + v - g_ * s) /  (g_ * (g_ + h_)),
                            (r_ + v + h_ * s) / (h_ * (g_ + h_)),
                            x)
      - log_incomplete_beta(r_ / (g_ * (g_ + h_)), r_ / (h_ * (g_ + h_)), x);
}

double BetaBinomialMixture::s_upper_bound(const double v) const {
  return v / g_;
}

double PolyStitchingBound::operator()(double v, double alpha) const {
  double use_v = std::max(v, v_min_);
  double ell = s_ * log(log(eta_ * use_v / v_min_)) + A_ + log(1 / alpha);
  double term2 = k2_ * c_ * ell;
  return sqrt(k1_ * k1_ * use_v * ell + term2 * term2) + term2;
}

double normal_log_mixture(const double s, const double v, const double v_opt,
                          const double alpha_opt,
                          const bool is_one_sided) {
  if (is_one_sided) {
    OneSidedNormalMixture mixture(v_opt, alpha_opt);
    return mixture.log_superMG(s, v);
  } else {
    TwoSidedNormalMixture mixture(v_opt, alpha_opt);
    return mixture.log_superMG(s, v);
  }
}

double normal_mixture_bound(
    const double v, const double alpha, const double v_opt,
    const double alpha_opt, const bool is_one_sided) {
  if (is_one_sided) {
    OneSidedNormalMixture mixture(v_opt, alpha_opt);
    return mixture.bound(v, log(1 / alpha));
  } else {
    TwoSidedNormalMixture mixture(v_opt, alpha_opt);
    return mixture.bound(v, log(1 / alpha));
  }
}

double gamma_exponential_log_mixture(
    const double s, const double v, const double v_opt,
    const double c, const double alpha_opt) {
  GammaExponentialMixture mixture(v_opt, alpha_opt, c);
  return mixture.log_superMG(s, v);
}

double gamma_exponential_mixture_bound(
    const double v, const double alpha, const double v_opt,
    const double c, const double alpha_opt) {
  GammaExponentialMixture mixture(v_opt, alpha_opt, c);
  return mixture.bound(v, log(1 / alpha));
}

double gamma_poisson_log_mixture(
    const double s, const double v, const double v_opt, const double c,
    const double alpha_opt) {
  GammaPoissonMixture mixture(v_opt, alpha_opt, c);
  return mixture.log_superMG(s, v);
}

double gamma_poisson_mixture_bound(
    const double v, const double alpha, const double v_opt, const double c,
    const double alpha_opt) {
  GammaPoissonMixture mixture(v_opt, alpha_opt, c);
  return mixture.bound(v, log(1 / alpha));
}

double beta_binomial_log_mixture(
    const double s, const double v, const double v_opt, const double g,
    const double h, const double alpha_opt,
    const bool is_one_sided) {
  BetaBinomialMixture mixture(v_opt, alpha_opt, g, h, is_one_sided);
  return mixture.log_superMG(s, v);
}

double beta_binomial_mixture_bound(
    const double v, const double alpha, const double v_opt, const double g,
    const double h, const double alpha_opt,
    const bool is_one_sided) {
  BetaBinomialMixture mixture(v_opt, alpha_opt, g, h, is_one_sided);
  return mixture.bound(v, log(1 / alpha));
}

double poly_stitching_bound(const double v, const double alpha,
                            const double v_min, const double c,
                            const double s, const double eta) {
  PolyStitchingBound bound(v_min, c, s, eta);
  return bound(v, alpha);
}

}; // namespace confseq

#endif // CONFIDENCESEQUENCES_UNIFORM_BOUNDARIES_H_
