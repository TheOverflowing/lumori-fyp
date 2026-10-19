// Preferences belong to an account; shared browser storage never supplies a global fallback.
export const generationPreferencesKey = userId => userId ? `zhixu.account.${encodeURIComponent(userId)}.generation` : null;
const agentReviewDefaultsVersion = 1;

export function createGenerationPreferences({ storage, onChange = () => {} } = {}) {
  let userId = null, queryFusion = false, autoExplore = false, useSubagents = false, autoReview = false, progressMode = 'detailed';
  const read = () => {
    let value;
    try { value = userId ? JSON.parse(storage?.getItem(generationPreferencesKey(userId)) || '{}') : {}; }
    catch { value = {}; }
    // Apply the requested defaults once per account, including legacy explicit
    // false values. The marker lets later deliberate opt-outs remain off.
    const migrate = Boolean(userId) && value?.agent_review_defaults_version !== agentReviewDefaultsVersion;
    return {queryFusion:value?.query_fusion === true, autoExplore:value?.auto_explore === true,
      useSubagents:migrate || value?.use_subagents === true, autoReview:migrate || value?.auto_review === true,
      progressMode:value?.progress_mode === 'simple' ? 'simple' : 'detailed', migrate};
  };
  const publish = changed => onChange({ userId, queryFusion, autoExplore, useSubagents, autoReview, progressMode, changed });
  const persist = () => {
    try { storage?.setItem(generationPreferencesKey(userId), JSON.stringify({query_fusion:queryFusion,
      auto_explore:autoExplore, use_subagents:useSubagents, auto_review:autoReview, progress_mode:progressMode,
      agent_review_defaults_version:agentReviewDefaultsVersion})); }
    catch { /* The current account keeps its preferences until the next sign-in. */ }
  };
  return {
    get queryFusion() { return queryFusion; },
    get autoExplore() { return autoExplore; },
    get useSubagents() { return useSubagents; },
    get autoReview() { return autoReview; },
    get progressMode() { return progressMode; },
    setAccount(id) {
      if (userId === (id || null)) return;
      userId = id || null;
      const next = read();
      ({queryFusion, autoExplore, useSubagents, autoReview, progressMode} = next);
      if (next.migrate) persist();
    },
    setQueryFusion(enabled) {
      if (!userId || queryFusion === (enabled === true)) return;
      queryFusion = enabled === true;
      persist();
      publish(['queryFusion']);
    },
    setAutoExplore(enabled) {
      if (!userId || autoExplore === (enabled === true)) return;
      autoExplore = enabled === true;
      persist();
      publish(['autoExplore']);
    },
    setUseSubagents(enabled) {
      if (!userId || useSubagents === (enabled === true)) return;
      useSubagents = enabled === true;
      persist();
      publish(['useSubagents']);
    },
    setAutoReview(enabled) {
      if (!userId || autoReview === (enabled === true)) return;
      autoReview = enabled === true;
      persist();
      publish(['autoReview']);
    },
    setProgressMode(mode) {
      if (!userId || !['simple','detailed'].includes(mode) || progressMode === mode) return;
      progressMode = mode;
      persist();
      publish(['progressMode']);
    },
    syncStorage(key) {
      if (!userId || (key !== null && key !== generationPreferencesKey(userId))) return;
      const next = read();
      const changed = [];
      if (next.queryFusion !== queryFusion) changed.push('queryFusion');
      if (next.autoExplore !== autoExplore) changed.push('autoExplore');
      if (next.useSubagents !== useSubagents) changed.push('useSubagents');
      if (next.autoReview !== autoReview) changed.push('autoReview');
      if (next.progressMode !== progressMode) changed.push('progressMode');
      ({queryFusion, autoExplore, useSubagents, autoReview, progressMode} = next);
      if (next.migrate) persist();
      if (changed.length) publish(changed);
    },
    requestFields(material) { return userId ? {...(queryFusion ? {query_fusion:true} : {}),
      ...(autoExplore ? {auto_explore:true} : {}),
      ...(autoReview ? {auto_review:true} : {}),
      ...(['quiz','assignment'].includes(material) ? {use_subagents:useSubagents} : {})} : {}; },
  };
}
