import six

from graphite.render.evaluator import evaluateTokens
from graphite.render.datalib import TimeSeries
from graphite.render.attime import parseTimeOffset
from graphite.functions.params import Param, ParamTypes

from datetime import timedelta

from .asap import smooth


def ASAP(requestContext, seriesList, resolution=1000):
    '''
    use the ASAP smoothing on a series
    https://arxiv.org/pdf/1703.00983.pdf
    https://raw.githubusercontent.com/stanford-futuredata/ASAP/master/ASAP.py
    :param requestContext:
    :param seriesList:
    :param resolution: either number of points to keep or a time resolution
    :return: smoothed(seriesList)
    '''

    if not seriesList:
        return []

    windowInterval = None
    if isinstance(resolution, six.string_types):
        delta = parseTimeOffset(resolution)
        windowInterval = abs(delta.seconds + (delta.days * 86400))

    if windowInterval:
        previewSeconds = windowInterval
    else:
        previewSeconds = max([s.step for s in seriesList]) * int(resolution)

    # ignore original data and pull new, including our preview
    # data from earlier is needed to calculate the early results
    newContext = requestContext.copy()
    newContext['startTime'] = (requestContext['startTime'] -
                               timedelta(seconds=previewSeconds))
    previewList = evaluateTokens(newContext, requestContext['args'][0])
    result = []
    for series in previewList:

        if windowInterval:
            # the resolution here is really the number of points to maintain
            # so we need to convert the "seconds" to num points
            windowPoints = round((series.end - series.start) / windowInterval)
        else:
            use_res = int(resolution)
            if len(series) < use_res:
                use_res = len(series)
            windowPoints = use_res

        if isinstance(resolution, six.string_types):
            newName = 'asap(%s,"%s")' % (series.name, resolution)
        else:
            newName = "asap(%s,%s)" % (series.name, resolution)

        step_guess = (series.end - series.start) // windowPoints

        newSeries = TimeSeries(
            newName,
            series.start,
            series.end,
            step_guess,
            []
        )
        newSeries.pathExpression = newName

        # detect "none" lists
        if len([v for v in series if v is not None]) <= 1:
            newSeries.extend(series)
        else:
            # the "resolution" is a suggestion,
            # the algo will alter it some inorder
            # to get the best view for things
            new_s = smooth(series, windowPoints)
            # steps need to be ints, so we must force the issue
            new_step = round((series.end - series.start) / len(new_s))
            newSeries.step = new_step
            newSeries.extend(new_s)
        result.append(newSeries)

    return result


# optionally set the group attribute
ASAP.group = 'Custom'
ASAP.params = [
  Param('seriesList', ParamTypes.seriesList, required=True),
  Param('resolution', ParamTypes.intOrInterval, required=False),
]

SeriesFunctions = {
  'asap': ASAP,
}
