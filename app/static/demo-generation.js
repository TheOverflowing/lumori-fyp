// The server marks the classroom account and its prepared course explicitly.
export function classroomGenerationDraft(session, courseId) {
  if (!session?.user?.id || !courseId || session.demo_course_id !== courseId) return null;
  return {
    material:'quiz', language:'en', question_type:'mcq', count:1,
    difficulty:'easy', difficulty_mode:'uniform',
    topic:'Identify the roles of observations, actions, rewards, and policies in reinforcement learning. Use only the selected course source.',
    learner_profile:'First-year computer science students who have read the introductory course material.',
    learner_profile_is_default:false, include_explanations:false,
    check_missing_details:false,
  };
}

export function classroomGenerationPreferences(preferences) {
  preferences.setAutoExplore(false);
  preferences.setQueryFusion(false);
  // Account initialization applies the agent/review defaults once. Reopening
  // the classroom draft must preserve a later explicit choice to turn them off.
}
