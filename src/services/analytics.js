/**
 * DevRescue AI - Analytics Service
 */

export const ANALYTICS_DATA = {
  overview: {
    successRate: '94.2%',
    avgTime: '3m 42s',
    testsPassed: '14,892',
    bugsResolved: '1,260',
    totalPrsMerged: '1,187',
    avgCostPerPatch: '$0.34',
    linesSaved: '48,200',
  },
  weeklyTrend: [
    { week: 'WK 34', resolved: 42, dispatched: 46, total: 46, rate: 91 },
    { week: 'WK 35', resolved: 48, dispatched: 52, total: 52, rate: 93 },
    { week: 'WK 36', resolved: 65, dispatched: 71, total: 71, rate: 92 },
    { week: 'WK 37', resolved: 78, dispatched: 82, total: 82, rate: 95 },
    { week: 'WK 38', resolved: 92, dispatched: 98, total: 98, rate: 94 },
    { week: 'WK 39', resolved: 110, dispatched: 115, total: 115, rate: 96 },
    { week: 'WK 40', resolved: 124, dispatched: 130, total: 130, rate: 95 },
  ],
  languageDistribution: [
    { language: 'TypeScript / JavaScript', percentage: 44, share: 44, count: 554, color: '#3B82F6' },
    { language: 'Rust', percentage: 22, share: 22, count: 277, color: '#F97316' },
    { language: 'Go', percentage: 18, share: 18, count: 227, color: '#06B6D4' },
    { language: 'Python', percentage: 16, share: 16, count: 202, color: '#10B981' },
  ],
  failureCategories: [
    {
      category: 'Concurrency & Deadlocks',
      count: 382,
      pct: '30%',
      example: 'Race conditions on shared mutex locks in worker event loop',
      resolutionRate: '98.1%'
    },
    {
      category: 'Unchecked Null & Option Unwraps',
      count: 320,
      pct: '25%',
      example: 'None / undefined unwrap on optional telemetry context',
      resolutionRate: '99.4%'
    },
    {
      category: 'Memory Leaks & Unclosed Handles',
      count: 240,
      pct: '19%',
      example: 'File descriptor leak in async worker stream',
      resolutionRate: '94.2%'
    },
    {
      category: 'Timestamp & Skew Boundary Math',
      count: 180,
      pct: '14%',
      example: 'UTC offset boundary truncation across nodes',
      resolutionRate: '96.8%'
    },
    {
      category: 'Off-By-One & Slice Parsing',
      count: 138,
      pct: '12%',
      example: 'Slice index overflow on packet chunk reassembly',
      resolutionRate: '99.0%'
    },
  ],
};
