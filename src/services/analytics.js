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
    avgCostPerPatch: '$0.41',
    linesSaved: '48,200',
  },
  weeklyTrend: [
    { week: 'WK 34', resolved: 42, rate: 91 },
    { week: 'WK 35', resolved: 48, rate: 93 },
    { week: 'WK 36', resolved: 65, rate: 92 },
    { week: 'WK 37', resolved: 78, rate: 95 },
    { week: 'WK 38', resolved: 92, rate: 94 },
    { week: 'WK 39', resolved: 110, rate: 96 },
    { week: 'WK 40', resolved: 124, rate: 95 },
  ],
  languageDistribution: [
    { language: 'TypeScript / JavaScript', percentage: 44, count: 554 },
    { language: 'Rust', percentage: 22, count: 277 },
    { language: 'Go', percentage: 18, count: 227 },
    { language: 'Python', percentage: 16, count: 202 },
  ],
  failureCategories: [
    { category: 'Concurrency & Deadlocks', count: 382, pct: '30%' },
    { category: 'Unchecked Null & Option Unwraps', count: 320, pct: '25%' },
    { category: 'Memory Leaks & Unclosed Handles', count: 240, pct: '19%' },
    { category: 'Timestamp & Skew Boundary Math', count: 180, pct: '14%' },
    { category: 'Off-By-One & Slice Parsing', count: 138, pct: '12%' },
  ],
};
