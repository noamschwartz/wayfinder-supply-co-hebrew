export const TOOL_STATUS_MESSAGES: Record<string, string> = {
  'tool-workflow-check-trip-safety': 'בודק תנאי מזג אוויר...',
  'tool-workflow-get-customer-profile': 'מחפש את ההעדפות שלכם...',
  'tool-search-product-search': 'סורק את הקטלוג...',
  'tool-esql-get-user-affinity': 'בודק היסטוריית גלישה...',
};

export function getToolStatusMessage(toolId: string): string {
  return TOOL_STATUS_MESSAGES[toolId] || 'מתכנן את ההרפתקה שלכם...';
}

export const NARRATION_MESSAGES: Record<string, { message: string; icon: string }> = {
  'lexical_search': {
    message: 'מחפש עם BM25 (התאמת מילות מפתח)...',
    icon: '🔍'
  },
  'hybrid_search': {
    message: 'משלב חיפוש סמנטי + מילות מפתח...',
    icon: '🧠'
  },
  'agent_start': {
    message: 'סוכן AI מנתח את הבקשה שלכם...',
    icon: '🤖'
  },
  'tool_weather': {
    message: 'בודק תנאי מזג אוויר...',
    icon: '🌤️'
  },
  'tool_profile': {
    message: 'מחפש פרופיל לקוח...',
    icon: '👤'
  },
  'tool_search': {
    message: 'מחפש בקטלוג מוצרים...',
    icon: '📦'
  },
  'tool_affinity': {
    message: 'מנתח העדפות גלישה...',
    icon: '📊'
  },
  'personalized': {
    message: '!תוצאות מותאמות אישית לסגנון שלכם',
    icon: '✨'
  },
}
