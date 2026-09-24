import type { StatisticsArtifact } from '@/types/artifacts'

/**
 * Backend may return statistics in several shapes:
 * 1) { descriptive, correlations, outliers }  (API contract)
 * 2) { statistics: {...}, correlations?, outliers? }  (legacy nested)
 * 3) flat column -> stats map as the whole object
 */
export function normalizeStatisticsArtifact(
  raw: StatisticsArtifact | Record<string, unknown> | null | undefined,
): StatisticsArtifact {
  if (!raw || typeof raw !== 'object') {
    return { descriptive: {}, correlations: {}, outliers: {} }
  }

  const obj = raw as Record<string, unknown>

  // Shape 1 / partial: has descriptive key
  if ('descriptive' in obj || 'correlations' in obj || 'outliers' in obj) {
    let descriptive = obj.descriptive
    // Nested legacy: descriptive.statistics
    if (
      descriptive &&
      typeof descriptive === 'object' &&
      !Array.isArray(descriptive) &&
      'statistics' in (descriptive as Record<string, unknown>) &&
      typeof (descriptive as Record<string, unknown>).statistics === 'object'
    ) {
      descriptive = (descriptive as Record<string, unknown>).statistics
    }
    return {
      descriptive:
        descriptive && typeof descriptive === 'object'
          ? (descriptive as StatisticsArtifact['descriptive'])
          : {},
      correlations: (obj.correlations as StatisticsArtifact['correlations']) ?? {},
      outliers: (obj.outliers as StatisticsArtifact['outliers']) ?? {},
    }
  }

  // Shape 2: top-level nested "statistics"
  if (
    'statistics' in obj &&
    typeof obj.statistics === 'object' &&
    obj.statistics !== null
  ) {
    return {
      descriptive: obj.statistics as StatisticsArtifact['descriptive'],
      correlations: (obj.correlations as StatisticsArtifact['correlations']) ?? {},
      outliers: (obj.outliers as StatisticsArtifact['outliers']) ?? {},
    }
  }

  // Shape 3: treat whole object as column descriptive map
  return {
    descriptive: obj as StatisticsArtifact['descriptive'],
    correlations: {},
    outliers: {},
  }
}