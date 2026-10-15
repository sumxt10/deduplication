from statistics import quantiles


def percentile(values, fraction):
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    return quantiles(values, n=100, method="inclusive")[max(0, int(fraction * 100) - 1)]