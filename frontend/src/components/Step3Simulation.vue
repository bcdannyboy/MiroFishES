<template>
  <div class="simulation-panel">
    <!-- Top Control Bar -->
    <div class="control-bar">
      <div class="status-group">
        <div v-if="showProbabilisticShell" class="ensemble-status-card">
          <div class="ensemble-status-header">
            <span class="ensemble-eyebrow">Probabilistic</span>
            <span class="ensemble-badge mono">{{ ensembleId || 'PENDING' }}</span>
          </div>
          <div class="ensemble-status-title">Ensemble Runtime Monitor</div>
          <div class="ensemble-status-stats">
            <span class="stat">
              <span class="stat-label">RUNS</span>
              <span class="stat-value mono">{{ ensembleRunCount }}</span>
            </span>
            <span class="stat">
              <span class="stat-label">STATE</span>
              <span class="stat-value mono">{{ ensembleLifecycleStatus }}</span>
            </span>
            <span class="stat">
              <span class="stat-label">FOCUS</span>
              <span class="stat-value mono">{{ selectedRunId || '-' }}</span>
            </span>
          </div>
          <div
            v-if="probabilisticStatusCountEntries.length > 0"
            class="ensemble-status-breakdown"
          >
            <span
              v-for="entry in probabilisticStatusCountEntries"
              :key="entry.status"
              class="ensemble-status-chip"
            >
              {{ entry.label }} {{ entry.count }}
            </span>
          </div>
        </div>
        <div class="platform-status twitter" :class="{ active: runStatus.twitter_running, completed: runStatus.twitter_completed }">
          <div class="platform-header">
            <svg class="platform-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
            </svg>
            <span class="platform-name">Info Plaza</span>
            <span v-if="runStatus.twitter_completed" class="status-badge">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="3">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            </span>
          </div>
          <div class="platform-stats">
            <span class="stat">
              <span class="stat-label">ROUND</span>
              <span class="stat-value mono">{{ runStatus.twitter_current_round || 0 }}<span class="stat-total">/{{ runStatus.total_rounds || maxRounds || '-' }}</span></span>
            </span>
            <span class="stat">
              <span class="stat-label">Elapsed Time</span>
              <span class="stat-value mono">{{ twitterElapsedTime }}</span>
            </span>
            <span class="stat">
              <span class="stat-label">ACTS</span>
              <span class="stat-value mono">{{ runStatus.twitter_actions_count || 0 }}</span>
            </span>
          </div>
<div class="actions-tooltip">
            <div class="tooltip-title">Available Actions</div>
            <div class="tooltip-actions">
              <span class="tooltip-action">POST</span>
              <span class="tooltip-action">LIKE</span>
              <span class="tooltip-action">REPOST</span>
              <span class="tooltip-action">QUOTE</span>
              <span class="tooltip-action">FOLLOW</span>
              <span class="tooltip-action">IDLE</span>
            </div>
          </div>
        </div>
        <div class="platform-status reddit" :class="{ active: runStatus.reddit_running, completed: runStatus.reddit_completed }">
          <div class="platform-header">
            <svg class="platform-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
            </svg>
            <span class="platform-name">Topic Community</span>
            <span v-if="runStatus.reddit_completed" class="status-badge">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="3">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            </span>
          </div>
          <div class="platform-stats">
            <span class="stat">
              <span class="stat-label">ROUND</span>
              <span class="stat-value mono">{{ runStatus.reddit_current_round || 0 }}<span class="stat-total">/{{ runStatus.total_rounds || maxRounds || '-' }}</span></span>
            </span>
            <span class="stat">
              <span class="stat-label">Elapsed Time</span>
              <span class="stat-value mono">{{ redditElapsedTime }}</span>
            </span>
            <span class="stat">
              <span class="stat-label">ACTS</span>
              <span class="stat-value mono">{{ runStatus.reddit_actions_count || 0 }}</span>
            </span>
          </div>
<div class="actions-tooltip">
            <div class="tooltip-title">Available Actions</div>
            <div class="tooltip-actions">
              <span class="tooltip-action">POST</span>
              <span class="tooltip-action">COMMENT</span>
              <span class="tooltip-action">LIKE</span>
              <span class="tooltip-action">DISLIKE</span>
              <span class="tooltip-action">SEARCH</span>
              <span class="tooltip-action">TREND</span>
              <span class="tooltip-action">FOLLOW</span>
              <span class="tooltip-action">MUTE</span>
              <span class="tooltip-action">REFRESH</span>
              <span class="tooltip-action">IDLE</span>
            </div>
          </div>
        </div>
      </div>

      <div class="action-controls">
        <button
          v-if="showProbabilisticShell"
          class="action-btn secondary"
          data-testid="probabilistic-start-button"
          :disabled="!canLaunchSelectedProbabilisticRun"
          @click="startProbabilisticRun"
        >
          {{ probabilisticStartButtonLabel }}
        </button>
        <button
          v-if="showProbabilisticShell"
          class="action-btn secondary"
          :disabled="!canStopSelectedProbabilisticRun"
          @click="handleStopSimulation"
        >
          {{ probabilisticStopButtonLabel }}
        </button>
        <button
          v-if="showProbabilisticShell"
          class="action-btn secondary"
          data-testid="probabilistic-cleanup-button"
          :disabled="!canCleanupSelectedProbabilisticRun"
          @click="cleanupSelectedProbabilisticRun"
        >
          {{ probabilisticCleanupButtonLabel }}
        </button>
        <button
          v-if="showProbabilisticShell"
          class="action-btn secondary"
          data-testid="probabilistic-rerun-button"
          :disabled="!canRerunSelectedProbabilisticRun"
          @click="rerunSelectedProbabilisticRun"
        >
          {{ probabilisticRerunButtonLabel }}
        </button>
        <button
          class="action-btn primary"
          :disabled="phase !== 2 || isGeneratingReport || !step3ReportState.enabled"
          @click="handleNextStep"
        >
          <span v-if="isGeneratingReport" class="loading-spinner-small"></span>
          {{ isGeneratingReport ? 'Starting...' : step3ReportState.buttonLabel }}
          <span v-if="step3ReportState.enabled && !isGeneratingReport" class="arrow-icon">-></span>
        </button>
        <span v-if="!step3ReportState.enabled" class="runtime-note">
          {{ step3ReportState.helperText }}
        </span>
      </div>
    </div>

    <!-- Main Content: Dual Timeline -->
    <div class="main-content-area" ref="scrollContainer">
      <div v-if="showProbabilisticShell" class="probabilistic-shell" data-testid="probabilistic-step3-shell">
        <div class="probabilistic-card">
          <div class="probabilistic-card-header">
            <span class="probabilistic-card-title">Stored Run Shell</span>
            <span class="probabilistic-card-meta mono">{{ selectedRunId || '-' }}</span>
          </div>
          <p class="probabilistic-copy">
            Step 3 is monitoring one stored probabilistic run. This surface shows raw runtime status and action
            history only. It does not imply calibrated probabilities or full ensemble-grounded reporting on its own.
          </p>
          <div v-if="probabilisticRunSummaries.length > 0" class="probabilistic-run-browser">
            <div class="probabilistic-run-browser-header">
              <span class="metric-label">Stored Runs</span>
              <span class="probabilistic-card-meta mono">{{ probabilisticRunSummaries.length }} tracked</span>
            </div>
            <div class="probabilistic-run-list">
              <button
                v-for="run in probabilisticRunSummaries"
                :key="run.run_id"
                class="probabilistic-run-item"
                :class="{ active: run.run_id === selectedRunId }"
                @click="handleSelectProbabilisticRun(run.run_id)"
              >
                <span class="mono">{{ run.run_id }}</span>
                <span>{{ getProbabilisticRunStatusLabel(run) }}</span>
                <span class="mono">seed {{ getProbabilisticRunSeed(run) }}</span>
              </button>
            </div>
          </div>
          <div
            v-if="probabilisticSelectionNotice"
            class="probabilistic-status-panel tone-warning"
            data-testid="probabilistic-selection-notice"
          >
            <span class="metric-label">Run Selection</span>
            <p class="probabilistic-status-copy">{{ probabilisticSelectionNotice }}</p>
          </div>
          <div class="probabilistic-summary-grid">
            <div class="probabilistic-metric">
              <span class="metric-label">Ensemble</span>
              <span class="metric-value mono">{{ ensembleId || '-' }}</span>
            </div>
            <div class="probabilistic-metric">
              <span class="metric-label">Run</span>
              <span class="metric-value mono">{{ selectedRunId || '-' }}</span>
            </div>
            <div class="probabilistic-metric">
              <span class="metric-label">Storage</span>
              <span class="metric-value mono">{{ probabilisticStorageStatus }}</span>
            </div>
            <div class="probabilistic-metric">
              <span class="metric-label">Seed</span>
              <span class="metric-value mono">{{ selectedRunSeed }}</span>
            </div>
            <div class="probabilistic-metric">
              <span class="metric-label">Lifecycle</span>
              <span class="metric-value mono">{{ selectedRunLifecycleStatus }}</span>
            </div>
            <div class="probabilistic-metric">
              <span class="metric-label">Progress</span>
              <span class="metric-value mono">{{ probabilisticProgressSummary }}</span>
            </div>
          </div>
          <div class="probabilistic-status-panel" :class="`tone-${probabilisticRunTone}`">
            <span class="metric-label">Run State</span>
            <p class="probabilistic-status-copy">{{ probabilisticRunNotice }}</p>
          </div>
          <div
            class="probabilistic-status-panel tone-neutral"
            data-testid="probabilistic-operator-guidance"
          >
            <span class="metric-label">Operator Guidance</span>
            <p class="probabilistic-status-copy">{{ probabilisticOperatorGuidance }}</p>
          </div>
          <div
            v-if="probabilisticPlatformSkewNotice"
            class="probabilistic-status-panel tone-warning"
            data-testid="probabilistic-platform-skew-notice"
          >
            <span class="metric-label">Platform Skew</span>
            <p class="probabilistic-status-copy">{{ probabilisticPlatformSkewNotice }}</p>
          </div>
          <div v-if="probabilisticTimelinePreview.length > 0" class="probabilistic-timeline-panel">
            <div class="probabilistic-timeline-header">
              <span class="metric-label">Recent Action Rounds</span>
              <span class="probabilistic-card-meta mono">{{ probabilisticActionRoundsMeta }}</span>
            </div>
            <div class="probabilistic-timeline-list">
              <div
                v-for="entry in probabilisticTimelinePreview"
                :key="`timeline-${entry.round_num}`"
                class="probabilistic-timeline-row"
              >
                <span class="mono">R{{ entry.round_num }}</span>
                <span>{{ formatTimelineSummary(entry) }}</span>
              </div>
            </div>
          </div>
          <div v-if="probabilisticRuntimeError" class="probabilistic-error">
            {{ probabilisticRuntimeError }}
          </div>
        </div>
        <div class="probabilistic-card probabilistic-analytics-card" data-testid="probabilistic-analytics-card">
          <div class="probabilistic-card-header">
            <span class="probabilistic-card-title">Observed Ensemble Analytics</span>
            <span class="probabilistic-card-meta mono">{{ probabilisticAnalyticsStamp }}</span>
          </div>
          <p class="probabilistic-copy">
            These cards read the currently persisted ensemble artifacts only. They remain empirical and
            observational, can be partial while runs are incomplete, and do not imply Step 4 report readiness.
          </p>
          <div class="probabilistic-analytics-grid">
            <div
              v-for="entry in probabilisticAnalyticsEntries"
              :key="entry.key"
              class="probabilistic-analytics-section"
              :class="`tone-${getAnalyticsCardTone(entry.card.status)}`"
            >
              <div class="probabilistic-analytics-header">
                <span class="metric-label">{{ entry.title }}</span>
                <span class="probabilistic-card-meta">{{ formatAnalyticsStatus(entry.card.status) }}</span>
              </div>
              <div class="probabilistic-analytics-headline">{{ entry.card.headline }}</div>
              <p class="probabilistic-analytics-body">{{ entry.card.body }}</p>
              <div
                v-if="entry.card.warnings && entry.card.warnings.length"
                class="probabilistic-warning-list"
              >
                <span
                  v-for="warning in entry.card.warnings"
                  :key="`${entry.key}-${warning}`"
                  class="probabilistic-warning-chip"
                >
                  {{ warning }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Timeline Header -->
      <div class="timeline-header" v-if="allActions.length > 0">
        <div class="timeline-stats">
          <span v-if="showProbabilisticShell" class="total-count">RUN: <span class="mono">{{ selectedRunId || '-' }}</span></span>
          <span class="total-count">TOTAL EVENTS: <span class="mono">{{ allActions.length }}</span></span>
          <span class="platform-breakdown">
            <span class="breakdown-item twitter">
              <svg class="mini-icon" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
              <span class="mono">{{ twitterActionsCount }}</span>
            </span>
            <span class="breakdown-divider">/</span>
            <span class="breakdown-item reddit">
              <svg class="mini-icon" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
              <span class="mono">{{ redditActionsCount }}</span>
            </span>
          </span>
        </div>
      </div>

      <!-- Timeline Feed -->
      <div class="timeline-feed">
        <div class="timeline-axis"></div>

        <TransitionGroup name="timeline-item">
          <div
            v-for="action in chronologicalActions"
            :key="action._uniqueId || action.id || `${action.timestamp}-${action.agent_id}`"
            class="timeline-item"
            :class="action.platform"
          >
            <div class="timeline-marker">
              <div class="marker-dot"></div>
            </div>

            <div class="timeline-card">
              <div class="card-header">
                <div class="agent-info">
                  <div class="avatar-placeholder">{{ (action.agent_name || 'A')[0] }}</div>
                  <span class="agent-name">{{ action.agent_name }}</span>
                </div>

                <div class="header-meta">
                  <div class="platform-indicator">
                    <svg v-if="action.platform === 'twitter'" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
                    <svg v-else viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
                  </div>
                  <div class="action-badge" :class="getActionTypeClass(action.action_type)">
                    {{ getActionTypeLabel(action.action_type) }}
                  </div>
                </div>
              </div>

              <div class="card-body">
<div v-if="action.action_type === 'CREATE_POST' && action.action_args?.content" class="content-text main-text">
                  {{ action.action_args.content }}
                </div>
<template v-if="action.action_type === 'QUOTE_POST'">
                  <div v-if="action.action_args?.quote_content" class="content-text">
                    {{ action.action_args.quote_content }}
                  </div>
                  <div v-if="action.action_args?.original_content" class="quoted-block">
                    <div class="quote-header">
                      <svg class="icon-small" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
                      <span class="quote-label">@{{ action.action_args.original_author_name || 'User' }}</span>
                    </div>
                    <div class="quote-text">
                      {{ truncateContent(action.action_args.original_content, 150) }}
                    </div>
                  </div>
                </template>
<template v-if="action.action_type === 'REPOST'">
                  <div class="repost-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="17 1 21 5 17 9"></polyline><path d="M3 11V9a4 4 0 0 1 4-4h14"></path><polyline points="7 23 3 19 7 15"></polyline><path d="M21 13v2a4 4 0 0 1-4 4H3"></path></svg>
                    <span class="repost-label">Reposted from @{{ action.action_args?.original_author_name || 'User' }}</span>
                  </div>
                  <div v-if="action.action_args?.original_content" class="repost-content">
                    {{ truncateContent(action.action_args.original_content, 200) }}
                  </div>
                </template>
<template v-if="action.action_type === 'LIKE_POST'">
                  <div class="like-info">
                    <svg class="icon-small filled" viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
                    <span class="like-label">Liked @{{ action.action_args?.post_author_name || 'User' }}'s post</span>
                  </div>
                  <div v-if="action.action_args?.post_content" class="liked-content">
                    "{{ truncateContent(action.action_args.post_content, 120) }}"
                  </div>
                </template>
<template v-if="action.action_type === 'CREATE_COMMENT'">
                  <div v-if="action.action_args?.content" class="content-text">
                    {{ action.action_args.content }}
                  </div>
                  <div v-if="action.action_args?.post_id" class="comment-context">
                    <svg class="icon-small" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
                    <span>Reply to post #{{ action.action_args.post_id }}</span>
                  </div>
                </template>
<template v-if="action.action_type === 'SEARCH_POSTS'">
                  <div class="search-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
                    <span class="search-label">Search Query:</span>
                    <span class="search-query">"{{ action.action_args?.query || '' }}"</span>
                  </div>
                </template>
<template v-if="action.action_type === 'FOLLOW'">
                  <div class="follow-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="8.5" cy="7" r="4"></circle><line x1="20" y1="8" x2="20" y2="14"></line><line x1="23" y1="11" x2="17" y2="11"></line></svg>
                    <span class="follow-label">Followed @{{ action.action_args?.target_user || action.action_args?.user_id || 'User' }}</span>
                  </div>
                </template>

                <!-- UPVOTE / DOWNVOTE -->
                <template v-if="action.action_type === 'UPVOTE_POST' || action.action_type === 'DOWNVOTE_POST'">
                  <div class="vote-info">
                    <svg v-if="action.action_type === 'UPVOTE_POST'" class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="18 15 12 9 6 15"></polyline></svg>
                    <svg v-else class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
                    <span class="vote-label">{{ action.action_type === 'UPVOTE_POST' ? 'Upvoted' : 'Downvoted' }} Post</span>
                  </div>
                  <div v-if="action.action_args?.post_content" class="voted-content">
                    "{{ truncateContent(action.action_args.post_content, 120) }}"
                  </div>
                </template>
<template v-if="action.action_type === 'DO_NOTHING'">
                  <div class="idle-info">
                    <svg class="icon-small" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                    <span class="idle-label">Action Skipped</span>
                  </div>
                </template>
<div v-if="!['CREATE_POST', 'QUOTE_POST', 'REPOST', 'LIKE_POST', 'CREATE_COMMENT', 'SEARCH_POSTS', 'FOLLOW', 'UPVOTE_POST', 'DOWNVOTE_POST', 'DO_NOTHING'].includes(action.action_type) && action.action_args?.content" class="content-text">
                  {{ action.action_args.content }}
                </div>
              </div>

              <div class="card-footer">
                <span class="time-tag">R{{ action.round_num }} - {{ formatActionTime(action.timestamp) }}</span>
                <!-- Platform tag removed as it is in header now -->
              </div>
            </div>
          </div>
        </TransitionGroup>

        <div v-if="allActions.length === 0" class="waiting-state">
          <div class="pulse-ring"></div>
          <span>{{ showProbabilisticShell ? probabilisticWaitingText : 'Waiting for agent actions...' }}</span>
        </div>
      </div>
    </div>

    <!-- Bottom Info / Logs -->
    <div class="system-logs">
      <div class="log-header">
        <span class="log-title">SIMULATION MONITOR</span>
        <span class="log-id">{{ monitorId }}</span>
      </div>
      <div class="log-content" ref="logContent">
        <div class="log-line" v-for="(log, idx) in systemLogs" :key="idx">
          <span class="log-time">{{ log.time }}</span>
          <span class="log-msg">{{ log.msg }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import {
  cleanupSimulationEnsembleRuns,
  getSimulationEnsembleClusters,
  getSimulationEnsembleRun,
  getSimulationEnsembleRunActions,
  getSimulationEnsembleStatus,
  getSimulationEnsembleRunStatus,
  getSimulationEnsembleSensitivity,
  getSimulationEnsembleSummary,
  getSimulationEnsembleRunTimeline,
  getPrepareCapabilities,
  getRunStatus,
  getRunStatusDetail,
  rerunSimulationEnsembleRun,
  startSimulation,
  startSimulationEnsembleRun,
  stopSimulation,
  stopSimulationEnsembleRun
} from '../api/simulation'
import { generateReport } from '../api/report'
import {
  buildReportGenerationRequest,
  buildProbabilisticRunStartRequest,
  buildSimulationRunRouteQuery,
  deriveProbabilisticActionRoundsMeta,
  deriveProbabilisticOperatorActions,
  deriveProbabilisticAnalyticsCards,
  deriveProbabilisticPlatformSkewCopy,
  deriveProbabilisticProgressSummary,
  deriveProbabilisticStep3Runtime,
  getProbabilisticRuntimeShellErrorMessage,
  getStep3ReportState,
  resolveProbabilisticRunSelection
} from '../utils/probabilisticRuntime'

const TERMINAL_PROBABILISTIC_STATUSES = new Set(['completed', 'stopped', 'failed', 'error'])
const PROBABILISTIC_FAILURE_STATUSES = new Set(['failed', 'error'])

const props = defineProps({
  simulationId: String,
  maxRounds: Number,
  runtimeMode: {
    type: String,
    default: 'legacy'
  },
  ensembleId: {
    type: String,
    default: null
  },
  runId: {
    type: String,
    default: null
  },
  minutesPerRound: {
    type: Number,
    default: 30
  },
  projectData: Object,
  graphData: Object,
  systemLogs: Array
})

const emit = defineEmits(['go-back', 'next-step', 'add-log', 'update-status'])

const router = useRouter()

// State
const isGeneratingReport = ref(false)
const phase = ref(0)
const isStarting = ref(false)
const isStopping = ref(false)
const isCleaning = ref(false)
const isRerunning = ref(false)
const runStatus = ref({})
const allActions = ref([])
const actionIds = ref(new Set())
const scrollContainer = ref(null)
const logContent = ref(null)

const ensembleId = ref('')
const selectedRunId = ref('')
const selectedRunDetail = ref(null)
const probabilisticEnsembleStatus = ref(null)
const probabilisticRunSummaries = ref([])
const probabilisticSelectionNotice = ref('')
const probabilisticTimeline = ref([])
const probabilisticRuntimeIssue = ref('')
const probabilisticTimelineIssue = ref('')
const probabilisticSummaryArtifact = ref(null)
const probabilisticClustersArtifact = ref(null)
const probabilisticSensitivityArtifact = ref(null)
const probabilisticAnalyticsLoading = ref({
  summary: false,
  clusters: false,
  sensitivity: false
})
const probabilisticAnalyticsErrors = ref({
  summary: '',
  clusters: '',
  sensitivity: ''
})
const prepareCapabilities = ref(null)

const prevTwitterRound = ref(0)
const prevRedditRound = ref(0)
const lastProbabilisticLifecycle = ref('')
const suppressNextProbabilisticAutoStart = ref(false)

let statusTimer = null
let detailTimer = null

const formatElapsedTime = (currentRound) => {
  if (!currentRound || currentRound <= 0) return '0h 0m'
  const totalMinutes = currentRound * props.minutesPerRound
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return `${hours}h ${minutes}m`
}

const getTimelineEntryCount = (entry, countKeys = []) => {
  for (const key of countKeys) {
    if (typeof entry?.[key] === 'number') {
      return entry[key]
    }
  }
  return 0
}

const formatTimelineSummary = (entry) => {
  const twitterCount = getTimelineEntryCount(entry, ['twitter_actions_count', 'twitter_actions'])
  const redditCount = getTimelineEntryCount(entry, ['reddit_actions_count', 'reddit_actions'])
  const totalCount = getTimelineEntryCount(
    entry,
    ['total_actions_count', 'total_actions']
  ) || twitterCount + redditCount

  return `${totalCount} actions (${twitterCount} plaza / ${redditCount} community)`
}

const step3ReportState = computed(() => (
  getStep3ReportState(props.runtimeMode, prepareCapabilities.value || {})
))

const probabilisticRuntimeState = computed(() => deriveProbabilisticStep3Runtime({
  runtimeMode: props.runtimeMode,
  ensembleId: ensembleId.value,
  runId: selectedRunId.value,
  runDetail: selectedRunDetail.value,
  runStatus: runStatus.value
}))

const requestedProbabilisticMode = computed(
  () => probabilisticRuntimeState.value.requestedProbabilisticMode
)

const showProbabilisticShell = computed(() => requestedProbabilisticMode.value)

const isProbabilisticMode = computed(
  () => probabilisticRuntimeState.value.isProbabilisticMode
)

const chronologicalActions = computed(() => {
  return [...allActions.value].sort((left, right) => {
    const leftTime = Date.parse(left.timestamp || '') || 0
    const rightTime = Date.parse(right.timestamp || '') || 0
    if (leftTime !== rightTime) {
      return leftTime - rightTime
    }

    const leftRound = Number(left.round_num || 0)
    const rightRound = Number(right.round_num || 0)
    if (leftRound !== rightRound) {
      return leftRound - rightRound
    }

    return String(left._uniqueId || '').localeCompare(String(right._uniqueId || ''))
  })
})

const twitterActionsCount = computed(() => (
  allActions.value.filter((action) => action.platform === 'twitter').length
))

const redditActionsCount = computed(() => (
  allActions.value.filter((action) => action.platform === 'reddit').length
))

const selectedRunLifecycleStatus = computed(() => (
  probabilisticRuntimeState.value.lifecycleStatus
))

const ensembleRunCount = computed(() => {
  if (!showProbabilisticShell.value) {
    return 0
  }

  return (
    probabilisticEnsembleStatus.value?.total_runs
    || probabilisticRunSummaries.value.length
    || (isProbabilisticMode.value ? 1 : 0)
  )
})

const ensembleLifecycleStatus = computed(() => (
  probabilisticEnsembleStatus.value?.ensemble_status
  || selectedRunLifecycleStatus.value
))

const probabilisticStatusCounts = computed(() => (
  probabilisticEnsembleStatus.value?.status_counts || {}
))

const probabilisticStatusCountEntries = computed(() => {
  const priorities = {
    running: 0,
    starting: 1,
    prepared: 2,
    completed: 3,
    stopped: 4,
    failed: 5,
    error: 5
  }

  return Object.entries(probabilisticStatusCounts.value)
    .filter(([, count]) => Number(count) > 0)
    .sort(([leftStatus], [rightStatus]) => {
      const leftPriority = priorities[leftStatus] ?? 6
      const rightPriority = priorities[rightStatus] ?? 6
      if (leftPriority !== rightPriority) {
        return leftPriority - rightPriority
      }
      return leftStatus.localeCompare(rightStatus)
    })
    .map(([status, count]) => ({
      status,
      count,
      label: status.replace(/_/g, ' ').toUpperCase()
    }))
})

const probabilisticStorageStatus = computed(() => (
  probabilisticRuntimeState.value.storageStatus
))

const selectedRunSeed = computed(() => (
  probabilisticRuntimeState.value.selectedRunSeed
))

const probabilisticRuntimeError = computed(() => (
  probabilisticRuntimeIssue.value || probabilisticRuntimeState.value.runtimeError
))

const probabilisticWaitingText = computed(() => {
  if (probabilisticTimelineIssue.value) {
    return `Timeline inspection is unavailable: ${probabilisticTimelineIssue.value}`
  }
  return probabilisticRuntimeState.value.waitingText
})

const probabilisticTimelineCount = computed(() => probabilisticTimeline.value.length)

const latestTimelineEntry = computed(() => (
  probabilisticTimeline.value.length
    ? probabilisticTimeline.value[probabilisticTimeline.value.length - 1]
    : null
))

const latestTimelineRound = computed(() => latestTimelineEntry.value?.round_num ?? null)

const probabilisticProgressSummary = computed(() => (
  deriveProbabilisticProgressSummary({
    runStatus: runStatus.value,
    latestTimelineRound: latestTimelineRound.value,
    maxRounds: props.maxRounds
  })
))

const probabilisticActionRoundsMeta = computed(() => {
  if (probabilisticTimelineIssue.value) {
    return 'Unavailable'
  }
  return deriveProbabilisticActionRoundsMeta({
    timeline: probabilisticTimeline.value
  })
})

const probabilisticPlatformSkewNotice = computed(() => {
  const skewCopy = deriveProbabilisticPlatformSkewCopy({
    runStatus: runStatus.value
  })

  if (!skewCopy) {
    return ''
  }

  return `${skewCopy} Recent action rounds can be one-platform-only while the trailing platform catches up.`
})

const probabilisticTimelinePreview = computed(() => (
  [...probabilisticTimeline.value].slice(-4).reverse()
))

const probabilisticAnalyticsCards = computed(() => deriveProbabilisticAnalyticsCards({
  summaryArtifact: probabilisticSummaryArtifact.value,
  clustersArtifact: probabilisticClustersArtifact.value,
  sensitivityArtifact: probabilisticSensitivityArtifact.value,
  loadingByKey: probabilisticAnalyticsLoading.value,
  errorByKey: probabilisticAnalyticsErrors.value
}))

const probabilisticAnalyticsEntries = computed(() => ([
  {
    key: 'summary',
    title: 'Aggregate Summary',
    card: probabilisticAnalyticsCards.value.summary
  },
  {
    key: 'clusters',
    title: 'Scenario Clusters',
    card: probabilisticAnalyticsCards.value.clusters
  },
  {
    key: 'sensitivity',
    title: 'Sensitivity',
    card: probabilisticAnalyticsCards.value.sensitivity
  }
]))

const probabilisticAnalyticsStamp = computed(() => {
  const timestamps = [
    probabilisticSummaryArtifact.value?.generated_at,
    probabilisticClustersArtifact.value?.generated_at,
    probabilisticSensitivityArtifact.value?.generated_at
  ].filter(Boolean)

  if (!timestamps.length) {
    return 'PERSISTED'
  }

  return timestamps.sort().at(-1)
})

const monitorId = computed(() => {
  if (showProbabilisticShell.value) {
    return `${ensembleId.value || 'missing-ensemble'}:${selectedRunId.value || 'missing-run'}`
  }
  return props.simulationId || 'UNSET'
})

const probabilisticRunTone = computed(() => {
  if (probabilisticRuntimeError.value || PROBABILISTIC_FAILURE_STATUSES.has(selectedRunLifecycleStatus.value)) {
    return 'error'
  }
  if (selectedRunLifecycleStatus.value === 'stopped') {
    return 'warning'
  }
  if (selectedRunLifecycleStatus.value === 'completed') {
    return 'success'
  }
  return 'neutral'
})

const probabilisticOperatorActions = computed(() => deriveProbabilisticOperatorActions({
  lifecycleStatus: selectedRunLifecycleStatus.value,
  isStarting: isStarting.value,
  isStopping: isStopping.value,
  isCleaning: isCleaning.value,
  isRerunning: isRerunning.value
}))

const probabilisticRunNotice = computed(() => {
  if (probabilisticRuntimeError.value) {
    return probabilisticRuntimeError.value
  }

  if (!isProbabilisticMode.value) {
    return 'Step 3 is in the legacy single-run path.'
  }

  const runLabel = selectedRunId.value || 'stored run'
  const timelineSuffix = probabilisticTimelineIssue.value
    ? ` Timeline inspection is unavailable: ${probabilisticTimelineIssue.value}`
    : ''

  switch (selectedRunLifecycleStatus.value) {
    case 'starting':
      return `Stored run ${runLabel} is starting. Timeline rows will appear once round output is written.${timelineSuffix}`
    case 'running':
      return `Stored run ${runLabel} is running. Step 3 shows raw runtime status, actions, and action-bearing round timeline data only.${timelineSuffix}`
    case 'completed':
      return step3ReportState.value.enabled
        ? `Stored run ${runLabel} completed. Raw traces stay available here, and Step 4 can add observed empirical ensemble context from stored artifacts.${timelineSuffix}`
        : `Stored run ${runLabel} completed. Raw traces stay available here, while Step 4 report generation remains legacy-only for this probabilistic runtime path.${timelineSuffix}`
    case 'stopped':
      return `Stored run ${runLabel} stopped before completion. Raw traces remain visible, and this stored shell can be rerun without changing the original prepared inputs.${timelineSuffix}`
    case 'failed':
    case 'error':
      return `Stored run ${runLabel} entered ${selectedRunLifecycleStatus.value}. Step 3 exposes the raw trace only; cleanup and rerun remain available from the stored shell.${timelineSuffix}`
    default:
      return `Stored run shell ${runLabel} is prepared. Step 3 will launch it with the current max-round setting.${timelineSuffix}`
  }
})

const canLaunchSelectedProbabilisticRun = computed(() => (
  showProbabilisticShell.value
  && Boolean(selectedRunId.value)
  && probabilisticOperatorActions.value.start.enabled
))

const canStopSelectedProbabilisticRun = computed(() => (
  showProbabilisticShell.value
  && Boolean(selectedRunId.value)
  && probabilisticOperatorActions.value.stop.enabled
))

const canCleanupSelectedProbabilisticRun = computed(() => (
  showProbabilisticShell.value
  && Boolean(selectedRunId.value)
  && probabilisticOperatorActions.value.cleanup.enabled
))

const canRerunSelectedProbabilisticRun = computed(() => (
  showProbabilisticShell.value
  && Boolean(selectedRunId.value)
  && probabilisticOperatorActions.value.rerun.enabled
))

const probabilisticStartButtonLabel = computed(() => {
  return probabilisticOperatorActions.value.start.label
})

const probabilisticStopButtonLabel = computed(() => (
  probabilisticOperatorActions.value.stop.label
))

const probabilisticCleanupButtonLabel = computed(() => (
  probabilisticOperatorActions.value.cleanup.label
))

const probabilisticRerunButtonLabel = computed(() => (
  probabilisticOperatorActions.value.rerun.label
))

const probabilisticOperatorGuidance = computed(() => (
  probabilisticOperatorActions.value.guidance
))

const twitterElapsedTime = computed(() => (
  formatElapsedTime(runStatus.value.twitter_current_round || 0)
))

const redditElapsedTime = computed(() => (
  formatElapsedTime(runStatus.value.reddit_current_round || 0)
))

// Methods
const addLog = (msg) => {
  emit('add-log', msg)
}

const loadPrepareCapabilities = async () => {
  if (!requestedProbabilisticMode.value && !isProbabilisticMode.value) {
    prepareCapabilities.value = null
    return
  }

  try {
    const res = await getPrepareCapabilities()
    if (res?.success && res.data) {
      prepareCapabilities.value = res.data
    }
  } catch (err) {
    console.warn('Failed to load probabilistic capability state:', err)
  }
}

const syncProbabilisticIdsFromProps = () => {
  ensembleId.value = typeof props.ensembleId === 'string' ? props.ensembleId.trim() : ''
  selectedRunId.value = typeof props.runId === 'string' ? props.runId.trim() : ''
}

const resetRunViewState = () => {
  runStatus.value = {}
  allActions.value = []
  actionIds.value = new Set()
  prevTwitterRound.value = 0
  prevRedditRound.value = 0
  probabilisticEnsembleStatus.value = null
  probabilisticRunSummaries.value = []
  probabilisticSelectionNotice.value = ''
  selectedRunDetail.value = null
  probabilisticTimeline.value = []
  probabilisticTimelineIssue.value = ''
  probabilisticSummaryArtifact.value = null
  probabilisticClustersArtifact.value = null
  probabilisticSensitivityArtifact.value = null
  probabilisticAnalyticsLoading.value = {
    summary: false,
    clusters: false,
    sensitivity: false
  }
  probabilisticAnalyticsErrors.value = {
    summary: '',
    clusters: '',
    sensitivity: ''
  }
  lastProbabilisticLifecycle.value = ''
}

const resetAllState = () => {
  phase.value = 0
  isGeneratingReport.value = false
  isStarting.value = false
  isStopping.value = false
  isCleaning.value = false
  isRerunning.value = false
  probabilisticRuntimeIssue.value = ''
  resetRunViewState()
  syncProbabilisticIdsFromProps()
  stopPolling()
}

const buildProbabilisticRouteQuery = (runId) => buildSimulationRunRouteQuery({
  maxRounds: props.maxRounds,
  runtimeMode: props.runtimeMode,
  ensembleId: ensembleId.value,
  runId
})

const updateSelectedProbabilisticRun = async (
  runId,
  {
    suppressAutoStart = true
  } = {}
) => {
  if (!runId || !props.simulationId || !ensembleId.value) {
    return
  }

  if (suppressAutoStart) {
    suppressNextProbabilisticAutoStart.value = true
  }

  selectedRunId.value = runId
  await router.replace({
    name: 'SimulationRun',
    params: {
      simulationId: props.simulationId
    },
    query: buildProbabilisticRouteQuery(runId)
  })
}

const getProbabilisticRunStatusLabel = (run) => (
  run?.runner_status
  || run?.storage_status
  || run?.status
  || 'prepared'
)

const getProbabilisticRunSeed = (run) => (
  run?.seed_metadata?.resolution_seed
  ?? run?.seed_metadata?.root_seed
  ?? run?.root_seed
  ?? '-'
)

const handleSelectProbabilisticRun = async (runId) => {
  if (!runId || runId === selectedRunId.value) {
    return
  }

  probabilisticSelectionNotice.value = ''
  addLog(`Switching Step 3 focus to stored run ${runId}.`)
  await updateSelectedProbabilisticRun(runId)
}

const buildActionUniqueId = (action, index = 0) => (
  action.id
  || `${selectedRunId.value || props.simulationId}-${action.timestamp}-${action.platform}-${action.agent_id}-${action.action_type}-${index}`
)

const logRoundProgress = (data) => {
  if (data.twitter_current_round > prevTwitterRound.value) {
    addLog(
      `[Plaza] R${data.twitter_current_round}/${data.total_rounds} | `
      + `T:${data.twitter_simulated_hours || 0}h | `
      + `A:${data.twitter_actions_count || 0}`
    )
    prevTwitterRound.value = data.twitter_current_round
  }

  if (data.reddit_current_round > prevRedditRound.value) {
    addLog(
      `[Community] R${data.reddit_current_round}/${data.total_rounds} | `
      + `T:${data.reddit_simulated_hours || 0}h | `
      + `A:${data.reddit_actions_count || 0}`
    )
    prevRedditRound.value = data.reddit_current_round
  }
}

const doStartSimulation = async () => {
  if (!props.simulationId) {
    addLog('Error: missing simulationId')
    return
  }

  resetRunViewState()
  isStarting.value = true
  addLog('Starting the dual-platform parallel simulation...')
  emit('update-status', 'processing')

  try {
    const params = {
      simulation_id: props.simulationId,
      platform: 'parallel',
      force: true,
      enable_graph_memory_update: true
    }

    if (props.maxRounds) {
      params.max_rounds = props.maxRounds
      addLog(`Set maximum simulation rounds: ${props.maxRounds}`)
    }

    addLog('Dynamic graph update mode enabled')

    const res = await startSimulation(params)

    if (res.success && res.data) {
      if (res.data.force_restarted) {
        addLog('OK Cleared old simulation logs and restarted the simulation')
      }
      addLog('OK Simulation engine started successfully')
      addLog(`  - PID: ${res.data.process_pid || '-'}`)

      phase.value = 1
      runStatus.value = res.data

      startStatusPolling()
      startDetailPolling()
    } else {
      addLog(`X Startup failed: ${res.error || 'Unknown error'}`)
      emit('update-status', 'error')
    }
  } catch (err) {
    addLog(`X Startup exception: ${err.message}`)
    emit('update-status', 'error')
  } finally {
    isStarting.value = false
  }
}

const handleStopSimulation = async () => {
  if (!props.simulationId) {
    return
  }

  isStopping.value = true
  addLog('Stopping the simulation...')

  try {
    if (isProbabilisticMode.value) {
      const res = await stopSimulationEnsembleRun(
        props.simulationId,
        ensembleId.value,
        selectedRunId.value
      )

      if (res.success && res.data) {
        addLog(`OK Stored run ${selectedRunId.value} stopped`)
        runStatus.value = res.data
        await fetchProbabilisticAnalytics()
        phase.value = 2
        stopPolling()
        emit('update-status', 'completed')
        return
      }

      addLog(`Stop failed: ${res.error || 'Unknown error'}`)
      return
    }

    const res = await stopSimulation({ simulation_id: props.simulationId })

    if (res.success) {
      addLog('OK Simulation stopped')
      phase.value = 2
      stopPolling()
      emit('update-status', 'completed')
    } else {
      addLog(`Stop failed: ${res.error || 'Unknown error'}`)
    }
  } catch (err) {
    addLog(`Stop exception: ${err.message}`)
  } finally {
    isStopping.value = false
  }
}

const cleanupSelectedProbabilisticRun = async () => {
  if (!props.simulationId || !ensembleId.value || !selectedRunId.value) {
    probabilisticRuntimeIssue.value = 'Cleanup requires an explicit stored run selection.'
    addLog(probabilisticRuntimeIssue.value)
    emit('update-status', 'error')
    return
  }

  isCleaning.value = true
  stopPolling()
  probabilisticRuntimeIssue.value = ''
  addLog(`Cleaning stored run ${selectedRunId.value}...`)

  try {
    const res = await cleanupSimulationEnsembleRuns(
      props.simulationId,
      ensembleId.value,
      {
        run_ids: [selectedRunId.value]
      }
    )

    if (!res.success || !res.data) {
      throw new Error(res.error || 'Failed to clean the selected probabilistic run')
    }

    allActions.value = []
    actionIds.value = new Set()
    probabilisticTimeline.value = []
    probabilisticTimelineIssue.value = ''

    addLog(`OK Stored run ${selectedRunId.value} cleaned and reset to prepared`)
    await fetchProbabilisticEnsembleStatus({ throwOnError: true })
    await fetchProbabilisticRunDetail({ throwOnError: true })
    await fetchProbabilisticRunStatus({ throwOnError: true })
    await fetchProbabilisticRunActions({ throwOnError: true })
    await fetchProbabilisticRunTimeline()
    await fetchProbabilisticAnalytics()
    phase.value = 0
    emit('update-status', 'ready')
  } catch (err) {
    const activeRunIds = err?.response?.data?.active_run_ids
    const activeRunSuffix = Array.isArray(activeRunIds) && activeRunIds.length
      ? ` Active run IDs: ${activeRunIds.join(', ')}.`
      : ''
    const errorMessage = err?.response?.data?.error || err.message || 'Cleanup failed'
    probabilisticRuntimeIssue.value = `${errorMessage}${activeRunSuffix}`
    addLog(`Probabilistic Step 3 cleanup failed: ${probabilisticRuntimeIssue.value}`)
    emit('update-status', 'error')
  } finally {
    isCleaning.value = false
  }
}

const rerunSelectedProbabilisticRun = async () => {
  if (!props.simulationId || !ensembleId.value || !selectedRunId.value) {
    probabilisticRuntimeIssue.value = 'Child rerun creation requires an explicit stored run selection.'
    addLog(probabilisticRuntimeIssue.value)
    emit('update-status', 'error')
    return
  }

  isRerunning.value = true
  stopPolling()
  probabilisticRuntimeIssue.value = ''
  const sourceRunId = selectedRunId.value
  addLog(`Creating child rerun from stored run ${sourceRunId}...`)

  try {
    const res = await rerunSimulationEnsembleRun(
      props.simulationId,
      ensembleId.value,
      sourceRunId
    )

    if (!res.success || !res.data?.run?.run_id) {
      throw new Error(res.error || 'Failed to create a child rerun for the selected run')
    }

    const childRunId = res.data.run.run_id
    suppressNextProbabilisticAutoStart.value = true
    addLog(`OK Created child rerun ${childRunId} from stored run ${sourceRunId}`)
    await updateSelectedProbabilisticRun(childRunId)
  } catch (err) {
    const errorMessage = err?.response?.data?.error || err.message || 'Child rerun failed'
    probabilisticRuntimeIssue.value = errorMessage
    addLog(`Probabilistic Step 3 rerun failed: ${errorMessage}`)
    emit('update-status', 'error')
  } finally {
    isRerunning.value = false
  }
}

const startStatusPolling = () => {
  if (statusTimer) {
    clearInterval(statusTimer)
  }
  statusTimer = setInterval(() => {
    if (isProbabilisticMode.value || requestedProbabilisticMode.value) {
      fetchProbabilisticEnsembleStatus()
      fetchProbabilisticRunStatus()
      return
    }
    fetchRunStatus()
  }, 2000)
}

const startDetailPolling = () => {
  if (detailTimer) {
    clearInterval(detailTimer)
  }
  detailTimer = setInterval(async () => {
    if (isProbabilisticMode.value || requestedProbabilisticMode.value) {
      const selectionChanged = await fetchProbabilisticEnsembleStatus()
      if (selectionChanged || !isProbabilisticMode.value) {
        return
      }
      await fetchProbabilisticRunDetail()
      await fetchProbabilisticRunStatus()
      await fetchProbabilisticRunActions()
      await fetchProbabilisticRunTimeline()
      await fetchProbabilisticAnalytics()
      return
    }
    fetchRunStatusDetail()
  }, 3000)
}

const stopPolling = () => {
  if (statusTimer) {
    clearInterval(statusTimer)
    statusTimer = null
  }
  if (detailTimer) {
    clearInterval(detailTimer)
    detailTimer = null
  }
}

const fetchProbabilisticEnsembleStatus = async ({ throwOnError = false } = {}) => {
  if (!props.simulationId || !ensembleId.value) {
    return false
  }

  try {
    const res = await getSimulationEnsembleStatus(
      props.simulationId,
      ensembleId.value,
      { limit: 200 }
    )

    if (!res.success || !res.data) {
      throw new Error(res.error || 'Failed to fetch ensemble runtime status')
    }

    probabilisticEnsembleStatus.value = res.data
    probabilisticRunSummaries.value = Array.isArray(res.data.runs) ? res.data.runs : []

    const previousRequestedRunId = selectedRunId.value
    const selection = resolveProbabilisticRunSelection({
      requestedRunId: previousRequestedRunId,
      runs: probabilisticRunSummaries.value
    })

    if (selection.selectionMode === 'fallback' && selection.selectedRunId) {
      probabilisticSelectionNotice.value = (
        `Stored run ${previousRequestedRunId} is unavailable. `
        + `Step 3 switched focus to ${selection.selectedRunId}.`
      )
      probabilisticRuntimeIssue.value = ''
      addLog(probabilisticSelectionNotice.value)
      await updateSelectedProbabilisticRun(selection.selectedRunId)
      return true
    }

    if (selection.selectionMode === 'empty') {
      probabilisticSelectionNotice.value = previousRequestedRunId
        ? `Stored run ${previousRequestedRunId} is unavailable and this ensemble has no remaining stored runs.`
        : 'This ensemble has no stored runs to inspect yet.'
      probabilisticRuntimeIssue.value = probabilisticSelectionNotice.value
      emit('update-status', 'error')
      return false
    }

    probabilisticSelectionNotice.value = ''
    probabilisticRuntimeIssue.value = ''
    return false
  } catch (err) {
    if (throwOnError) {
      throw err
    }
    console.warn('Failed to fetch probabilistic ensemble status:', err)
    return false
  }
}

const checkPlatformsCompleted = (data) => {
  if (!data) return false

  const twitterCompleted = data.twitter_completed === true
  const redditCompleted = data.reddit_completed === true

  const twitterEnabled = (data.twitter_actions_count > 0) || data.twitter_running || twitterCompleted
  const redditEnabled = (data.reddit_actions_count > 0) || data.reddit_running || redditCompleted

  if (!twitterEnabled && !redditEnabled) return false

  if (twitterEnabled && !twitterCompleted) return false
  if (redditEnabled && !redditCompleted) return false

  return true
}

const fetchRunStatus = async () => {
  if (!props.simulationId) return

  try {
    const res = await getRunStatus(props.simulationId)

    if (res.success && res.data) {
      const data = res.data
      runStatus.value = data
      logRoundProgress(data)

      const isCompleted = data.runner_status === 'completed' || data.runner_status === 'stopped'
      const platformsCompleted = checkPlatformsCompleted(data)

      if (isCompleted || platformsCompleted) {
        if (platformsCompleted && !isCompleted) {
          addLog('OK Detected that all platform simulations have finished')
        }
        addLog('OK Simulation completed')
        phase.value = 2
        stopPolling()
        emit('update-status', 'completed')
      }
    }
  } catch (err) {
    console.warn('Failed to fetch runtime status:', err)
  }
}

const applyProbabilisticStatus = (data) => {
  if (!data || typeof data !== 'object') {
    return
  }

  runStatus.value = data
  logRoundProgress(data)

  const lifecycleState = deriveProbabilisticStep3Runtime({
    runtimeMode: props.runtimeMode,
    ensembleId: ensembleId.value,
    runId: selectedRunId.value,
    runDetail: selectedRunDetail.value,
    runStatus: data
  })
  const lifecycleStatus = lifecycleState.lifecycleStatus

  if (selectedRunId.value && lifecycleStatus !== lastProbabilisticLifecycle.value) {
    addLog(`Stored run ${selectedRunId.value} status: ${lifecycleStatus}`)
    lastProbabilisticLifecycle.value = lifecycleStatus
  }

  if (lifecycleStatus === 'running' || lifecycleStatus === 'starting') {
    phase.value = 1
    emit('update-status', 'processing')
    return
  }

  if (TERMINAL_PROBABILISTIC_STATUSES.has(lifecycleStatus)) {
    phase.value = 2
    stopPolling()
    emit(
      'update-status',
      PROBABILISTIC_FAILURE_STATUSES.has(lifecycleStatus) ? 'error' : 'completed'
    )
    return
  }

  phase.value = 0
  emit('update-status', 'ready')
}

const fetchProbabilisticRunDetail = async ({ throwOnError = false } = {}) => {
  if (!props.simulationId || !ensembleId.value || !selectedRunId.value) return

  try {
    const res = await getSimulationEnsembleRun(
      props.simulationId,
      ensembleId.value,
      selectedRunId.value
    )

    if (!res.success || !res.data) {
      throw new Error(res.error || 'Failed to load the stored run shell')
    }

    selectedRunDetail.value = res.data
    if (res.data.runtime_status) {
      applyProbabilisticStatus(res.data.runtime_status)
    }
  } catch (err) {
    if (throwOnError) {
      throw err
    }
    console.warn('Failed to fetch probabilistic run detail:', err)
  }
}

const fetchProbabilisticRunStatus = async ({ throwOnError = false } = {}) => {
  if (!props.simulationId || !ensembleId.value || !selectedRunId.value) return

  try {
    const res = await getSimulationEnsembleRunStatus(
      props.simulationId,
      ensembleId.value,
      selectedRunId.value
    )

    if (!res.success || !res.data) {
      throw new Error(res.error || 'Failed to fetch run-scoped runtime status')
    }

    applyProbabilisticStatus(res.data)
  } catch (err) {
    if (throwOnError) {
      throw err
    }
    console.warn('Failed to fetch probabilistic run status:', err)
  }
}

const fetchProbabilisticRunActions = async ({ throwOnError = false } = {}) => {
  if (!props.simulationId || !ensembleId.value || !selectedRunId.value) return

  try {
    const res = await getSimulationEnsembleRunActions(
      props.simulationId,
      ensembleId.value,
      selectedRunId.value,
      { limit: 500 }
    )

    if (!res.success || !res.data) {
      throw new Error(res.error || 'Failed to fetch run-scoped actions')
    }

    const serverActions = Array.isArray(res.data.actions) ? res.data.actions : []
    allActions.value = serverActions.map((action, index) => ({
      ...action,
      _uniqueId: buildActionUniqueId(action, index)
    }))
    actionIds.value = new Set(allActions.value.map((action) => action._uniqueId))
  } catch (err) {
    if (throwOnError) {
      throw err
    }
    console.warn('Failed to fetch probabilistic run actions:', err)
  }
}

const fetchProbabilisticRunTimeline = async ({ throwOnError = false } = {}) => {
  if (!props.simulationId || !ensembleId.value || !selectedRunId.value) return

  try {
    const res = await getSimulationEnsembleRunTimeline(
      props.simulationId,
      ensembleId.value,
      selectedRunId.value
    )

    if (!res.success || !res.data) {
      throw new Error(res.error || 'Failed to fetch run-scoped timeline data')
    }

    probabilisticTimeline.value = Array.isArray(res.data.timeline) ? res.data.timeline : []
    probabilisticTimelineIssue.value = ''
  } catch (err) {
    probabilisticTimelineIssue.value = err.message
    if (throwOnError) {
      throw err
    }
    console.warn('Failed to fetch probabilistic run timeline:', err)
  }
}

const fetchProbabilisticAnalytics = async ({ throwOnError = false } = {}) => {
  if (!props.simulationId || !ensembleId.value) return

  probabilisticAnalyticsLoading.value = {
    summary: true,
    clusters: true,
    sensitivity: true
  }

  const nextErrors = {
    summary: '',
    clusters: '',
    sensitivity: ''
  }
  let firstError = null

  const requests = [
    {
      key: 'summary',
      loader: () => getSimulationEnsembleSummary(props.simulationId, ensembleId.value),
      assign: (payload) => {
        probabilisticSummaryArtifact.value = payload
      }
    },
    {
      key: 'clusters',
      loader: () => getSimulationEnsembleClusters(props.simulationId, ensembleId.value),
      assign: (payload) => {
        probabilisticClustersArtifact.value = payload
      }
    },
    {
      key: 'sensitivity',
      loader: () => getSimulationEnsembleSensitivity(props.simulationId, ensembleId.value),
      assign: (payload) => {
        probabilisticSensitivityArtifact.value = payload
      }
    }
  ]

  await Promise.all(requests.map(async ({ key, loader, assign }) => {
    try {
      const res = await loader()
      if (!res.success || !res.data) {
        throw new Error(res.error || `Failed to fetch ${key} artifact`)
      }
      assign(res.data)
    } catch (err) {
      nextErrors[key] = err.message
      if (!firstError) {
        firstError = err
      }
    }
  }))

  probabilisticAnalyticsErrors.value = nextErrors
  probabilisticAnalyticsLoading.value = {
    summary: false,
    clusters: false,
    sensitivity: false
  }

  if (throwOnError && firstError) {
    throw firstError
  }
}

const fetchRunStatusDetail = async () => {
  if (!props.simulationId) return

  try {
    const res = await getRunStatusDetail(props.simulationId)

    if (res.success && res.data) {
      const serverActions = res.data.all_actions || []

      serverActions.forEach(action => {
        const actionId = action.id || `${action.timestamp}-${action.platform}-${action.agent_id}-${action.action_type}`

        if (!actionIds.value.has(actionId)) {
          actionIds.value.add(actionId)
          allActions.value.push({
            ...action,
            _uniqueId: actionId
          })
        }
      })
    }
  } catch (err) {
    console.warn('Failed to fetch detailed status:', err)
  }
}

// Probabilistic Step 3 monitors the single stored run shell created in Step 2.
const startProbabilisticRun = async () => {
  if (!props.simulationId || !ensembleId.value || !selectedRunId.value) {
    probabilisticRuntimeIssue.value = probabilisticRuntimeState.value.runtimeError
      || 'Probabilistic Step 3 is missing the stored run identifiers from Step 2.'
    addLog(probabilisticRuntimeIssue.value)
    emit('update-status', 'error')
    return
  }

  isStarting.value = true
  suppressNextProbabilisticAutoStart.value = false
  probabilisticRuntimeIssue.value = ''
  addLog(
    probabilisticOperatorActions.value.start.intent === 'retry'
      ? `Retrying stored run ${selectedRunId.value} from ensemble ${ensembleId.value}...`
      : `Starting stored run ${selectedRunId.value} from ensemble ${ensembleId.value}...`
  )

  try {
    const payload = buildProbabilisticRunStartRequest({
      maxRounds: props.maxRounds
    })

    if (payload.max_rounds) {
      addLog(`Set maximum simulation rounds: ${props.maxRounds}`)
    }

    const res = await startSimulationEnsembleRun(
      props.simulationId,
      ensembleId.value,
      selectedRunId.value,
      payload
    )

    if (!res.success || !res.data) {
      throw new Error(res.error || 'Failed to start the stored probabilistic run')
    }

    addLog(`OK Stored run ${selectedRunId.value} launched in probabilistic Step 3`)
    applyProbabilisticStatus(res.data)
    await fetchProbabilisticRunDetail({ throwOnError: true })
    await fetchProbabilisticRunActions({ throwOnError: true })
    await fetchProbabilisticRunTimeline()
    await fetchProbabilisticAnalytics()
    startStatusPolling()
    startDetailPolling()
  } catch (err) {
    const errorMessage = getProbabilisticRuntimeShellErrorMessage(
      err,
      'Failed to start the stored probabilistic run'
    )
    probabilisticRuntimeIssue.value = errorMessage
    addLog(`Probabilistic Step 3 startup failed: ${errorMessage}`)
    emit('update-status', 'error')
  } finally {
    isStarting.value = false
  }
}

// Helpers
const getActionTypeLabel = (type) => {
  const labels = {
    'CREATE_POST': 'POST',
    'REPOST': 'REPOST',
    'LIKE_POST': 'LIKE',
    'CREATE_COMMENT': 'COMMENT',
    'LIKE_COMMENT': 'LIKE',
    'DO_NOTHING': 'IDLE',
    'FOLLOW': 'FOLLOW',
    'SEARCH_POSTS': 'SEARCH',
    'QUOTE_POST': 'QUOTE',
    'UPVOTE_POST': 'UPVOTE',
    'DOWNVOTE_POST': 'DOWNVOTE'
  }
  return labels[type] || type || 'UNKNOWN'
}

const getActionTypeClass = (type) => {
  const classes = {
    'CREATE_POST': 'badge-post',
    'REPOST': 'badge-action',
    'LIKE_POST': 'badge-action',
    'CREATE_COMMENT': 'badge-comment',
    'LIKE_COMMENT': 'badge-action',
    'QUOTE_POST': 'badge-post',
    'FOLLOW': 'badge-meta',
    'SEARCH_POSTS': 'badge-meta',
    'UPVOTE_POST': 'badge-action',
    'DOWNVOTE_POST': 'badge-action',
    'DO_NOTHING': 'badge-idle'
  }
  return classes[type] || 'badge-default'
}

const truncateContent = (content, maxLength = 100) => {
  if (!content) return ''
  if (content.length > maxLength) return content.substring(0, maxLength) + '...'
  return content
}

const formatActionTime = (timestamp) => {
  if (!timestamp) return ''
  try {
    return new Date(timestamp).toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch {
    return ''
  }
}

const formatAnalyticsStatus = (status) => {
  const labels = {
    loading: 'Loading',
    error: 'Error',
    empty: 'Empty',
    partial: 'Partial',
    complete: 'Complete'
  }
  return labels[status] || 'Observed'
}

const getAnalyticsCardTone = (status) => {
  if (status === 'error') {
    return 'error'
  }
  if (status === 'partial') {
    return 'warning'
  }
  if (status === 'complete') {
    return 'success'
  }
  return 'neutral'
}

const handleNextStep = async () => {
  if (!step3ReportState.value.enabled) {
    addLog(step3ReportState.value.helperText)
    return
  }

  if (!props.simulationId) {
    addLog('Error: missing simulationId')
    return
  }

  if (isGeneratingReport.value) {
    addLog('Report generation request sent. Please wait...')
    return
  }

  isGeneratingReport.value = true
  addLog('Starting report generation...')

  try {
    if (
      props.runtimeMode === 'probabilistic'
      && (!ensembleId.value || !selectedRunId.value)
    ) {
      addLog(
        probabilisticRuntimeState.value.runtimeError
        || 'Probabilistic Step 4 requires explicit ensemble and run identifiers from Step 3.'
      )
      isGeneratingReport.value = false
      return
    }

    const res = await generateReport(buildReportGenerationRequest({
      simulationId: props.simulationId,
      runtimeMode: props.runtimeMode,
      ensembleId: ensembleId.value,
      runId: selectedRunId.value,
      forceRegenerate: true
    }))

    if (res.success && res.data) {
      const reportId = res.data.report_id
      addLog(`OK Report generation task started: ${reportId}`)
      const reportRoute = {
        name: 'Report',
        params: { reportId }
      }
      const probabilisticQuery = buildSimulationRunRouteQuery({
        runtimeMode: props.runtimeMode,
        ensembleId: ensembleId.value,
        runId: selectedRunId.value
      })
      if (Object.keys(probabilisticQuery).length > 0) {
        reportRoute.query = probabilisticQuery
      }
      router.push(reportRoute)
    } else {
      addLog(`X Failed to start report generation: ${res.error || 'Unknown error'}`)
      isGeneratingReport.value = false
    }
  } catch (err) {
    addLog(`X Report generation startup exception: ${err.message}`)
    isGeneratingReport.value = false
  }
}

const initializeProbabilisticRun = async () => {
  const runtimeError = probabilisticRuntimeState.value.runtimeError
  if (runtimeError) {
    probabilisticRuntimeIssue.value = runtimeError
    addLog(runtimeError)
    emit('update-status', 'error')
    return
  }

  addLog(
    `Loading probabilistic Step 3 shell for ensemble ${ensembleId.value}, run ${selectedRunId.value}`
  )

  try {
    const selectionChanged = await fetchProbabilisticEnsembleStatus({ throwOnError: true })
    if (selectionChanged || !isProbabilisticMode.value) {
      return
    }

    await fetchProbabilisticRunDetail({ throwOnError: true })
    await fetchProbabilisticRunStatus({ throwOnError: true })
    await fetchProbabilisticRunActions({ throwOnError: true })
    await fetchProbabilisticRunTimeline()
    await fetchProbabilisticAnalytics()
    if (step3ReportState.value.helperText) {
      addLog(step3ReportState.value.helperText)
    }

    if (selectedRunLifecycleStatus.value === 'running' || selectedRunLifecycleStatus.value === 'starting') {
      phase.value = 1
      emit('update-status', 'processing')
      startStatusPolling()
      startDetailPolling()
      return
    }

    if (TERMINAL_PROBABILISTIC_STATUSES.has(selectedRunLifecycleStatus.value)) {
      phase.value = 2
      emit(
        'update-status',
        PROBABILISTIC_FAILURE_STATUSES.has(selectedRunLifecycleStatus.value) ? 'error' : 'completed'
      )
      return
    }

    if (suppressNextProbabilisticAutoStart.value) {
      suppressNextProbabilisticAutoStart.value = false
      phase.value = 0
      emit('update-status', 'ready')
      addLog(`Stored run shell ${selectedRunId.value} loaded. Launch it manually when ready.`)
      return
    }

    await startProbabilisticRun()
  } catch (err) {
    probabilisticRuntimeIssue.value = err.message
    addLog(`Probabilistic Step 3 initialization failed: ${err.message}`)
    emit('update-status', 'error')
  }
}

const initializeSimulationRun = async () => {
  addLog('Step3 simulation run initialized')
  resetAllState()

  if (!props.simulationId) {
    return
  }

  await loadPrepareCapabilities()

  if (requestedProbabilisticMode.value) {
    await initializeProbabilisticRun()
  } else {
    await doStartSimulation()
  }
}

// Scroll log to bottom
watch(() => props.systemLogs?.length, () => {
  nextTick(() => {
    if (logContent.value) {
      logContent.value.scrollTop = logContent.value.scrollHeight
    }
  })
})

watch(
  () => [
    props.simulationId,
    props.runtimeMode,
    props.ensembleId,
    props.runId,
    props.maxRounds
  ],
  () => {
    initializeSimulationRun()
  }
)

onMounted(() => {
  initializeSimulationRun()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.simulation-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #FFFFFF;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
  overflow: hidden;
}

/* --- Control Bar --- */
.control-bar {
  background: #FFF;
  padding: 12px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  border-bottom: 1px solid #EAEAEA;
  z-index: 10;
  min-height: 64px;
}

.status-group {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: stretch;
}

.action-controls {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.ensemble-status-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 220px;
  padding: 8px 12px;
  border-radius: 4px;
  border: 1px solid #D7DADF;
  background: linear-gradient(135deg, #F7F7F7 0%, #FFFFFF 100%);
}

.ensemble-status-header {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.ensemble-eyebrow {
  font-size: 10px;
  font-weight: 700;
  color: #4B5563;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.ensemble-badge {
  font-size: 11px;
  color: #111827;
}

.ensemble-status-title {
  font-size: 13px;
  font-weight: 700;
  color: #111827;
}

.ensemble-status-stats {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.ensemble-status-breakdown {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.ensemble-status-chip {
  padding: 3px 8px;
  border-radius: 999px;
  background: #F3F4F6;
  color: #374151;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.runtime-note {
  max-width: 320px;
  font-size: 11px;
  line-height: 1.45;
  color: #6B7280;
}

/* Platform Status Cards */
.platform-status {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 6px 12px;
  border-radius: 4px;
  background: #FAFAFA;
  border: 1px solid #EAEAEA;
  opacity: 0.7;
  transition: all 0.3s;
  min-width: 140px;
  position: relative;
  cursor: pointer;
}

.platform-status.active {
  opacity: 1;
  border-color: #333;
  background: #FFF;
}

.platform-status.completed {
  opacity: 1;
  border-color: #1A936F;
  background: #F2FAF6;
}

/* Actions Tooltip */
.actions-tooltip {
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  margin-top: 8px;
  padding: 10px 14px;
  background: #000;
  color: #FFF;
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  opacity: 0;
  visibility: hidden;
  transition: all 0.2s ease;
  z-index: 100;
  min-width: 180px;
  pointer-events: none;
}

.actions-tooltip::before {
  content: '';
  position: absolute;
  top: -6px;
  left: 50%;
  transform: translateX(-50%);
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-bottom: 6px solid #000;
}

.platform-status:hover .actions-tooltip {
  opacity: 1;
  visibility: visible;
}

.tooltip-title {
  font-size: 10px;
  font-weight: 600;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 8px;
}

.tooltip-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tooltip-action {
  font-size: 10px;
  font-weight: 600;
  padding: 3px 8px;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 2px;
  color: #FFF;
  letter-spacing: 0.03em;
}

.platform-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}

.platform-name {
  font-size: 11px;
  font-weight: 700;
  color: #000;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.platform-status.twitter .platform-icon { color: #000; }
.platform-status.reddit .platform-icon { color: #000; }

.platform-stats {
  display: flex;
  gap: 10px;
}

.stat {
  display: flex;
  align-items: baseline;
  gap: 3px;
}

.stat-label {
  font-size: 8px;
  color: #999;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.stat-value {
  font-size: 11px;
  font-weight: 600;
  color: #333;
}

.stat-total, .stat-unit {
  font-size: 9px;
  color: #999;
  font-weight: 400;
}

.status-badge {
  margin-left: auto;
  color: #1A936F;
  display: flex;
  align-items: center;
}

/* Action Button */
.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  font-size: 13px;
  font-weight: 600;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.action-btn.primary {
  background: #000;
  color: #FFF;
}

.action-btn.primary:hover:not(:disabled) {
  background: #333;
}

.action-btn.secondary {
  background: #F3F4F6;
  color: #111827;
}

.action-btn.secondary:hover:not(:disabled) {
  background: #E5E7EB;
}

.action-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* --- Main Content Area --- */
.main-content-area {
  flex: 1;
  overflow-y: auto;
  position: relative;
  background: #FFF;
}

.probabilistic-shell {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
  padding: 16px 24px 0;
}

.probabilistic-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border: 1px solid #E5E7EB;
  border-radius: 8px;
  background: #FCFCFC;
}

.probabilistic-run-browser {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.probabilistic-run-browser-header {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
}

.probabilistic-run-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 220px;
  overflow-y: auto;
}

.probabilistic-run-item {
  display: grid;
  grid-template-columns: minmax(48px, auto) minmax(0, 1fr) minmax(80px, auto);
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid #E5E7EB;
  border-radius: 6px;
  background: #FFFFFF;
  color: #111827;
  cursor: pointer;
  text-align: left;
  font-size: 12px;
}

.probabilistic-run-item:hover {
  border-color: #94A3B8;
  background: #F8FAFC;
}

.probabilistic-run-item.active {
  border-color: #111827;
  background: #F3F4F6;
}

.probabilistic-card-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: baseline;
}

.probabilistic-card-title {
  font-size: 13px;
  font-weight: 700;
  color: #111827;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

.probabilistic-card-meta {
  font-size: 11px;
  color: #4B5563;
}

.probabilistic-copy {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: #374151;
}

.probabilistic-form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}

.probabilistic-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 11px;
  font-weight: 600;
  color: #4B5563;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.probabilistic-field input,
.probabilistic-field select {
  border: 1px solid #D1D5DB;
  border-radius: 6px;
  padding: 10px 12px;
  font-size: 13px;
  color: #111827;
  background: #FFF;
}

.probabilistic-field input:disabled,
.probabilistic-field select:disabled {
  background: #F3F4F6;
  color: #6B7280;
}

.probabilistic-note {
  font-size: 12px;
  line-height: 1.5;
  color: #6B7280;
}

.probabilistic-error {
  padding: 10px 12px;
  border-radius: 6px;
  background: #FFF1F2;
  border: 1px solid #FBCFE8;
  color: #9F1239;
  font-size: 12px;
  line-height: 1.5;
}

.probabilistic-summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.probabilistic-status-panel,
.probabilistic-timeline-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border-radius: 6px;
  border: 1px solid #E5E7EB;
  background: #FFF;
}

.probabilistic-status-panel.tone-neutral {
  border-color: #E5E7EB;
  background: #FFF;
}

.probabilistic-status-panel.tone-warning {
  border-color: #FCD34D;
  background: #FFFBEA;
}

.probabilistic-status-panel.tone-success {
  border-color: #86EFAC;
  background: #F0FDF4;
}

.probabilistic-status-panel.tone-error {
  border-color: #FDA4AF;
  background: #FFF1F2;
}

.probabilistic-status-copy {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: #374151;
}

.probabilistic-timeline-header {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
}

.probabilistic-timeline-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.probabilistic-timeline-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 8px 10px;
  border-radius: 4px;
  background: #F9FAFB;
  color: #374151;
  font-size: 12px;
}

.probabilistic-metric {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 6px;
  background: #FFF;
  border: 1px solid #E5E7EB;
}

.probabilistic-run-meta {
  display: grid;
  grid-template-columns: auto 1fr auto 1fr;
  gap: 8px 12px;
  align-items: center;
}

.probabilistic-meta-label,
.metric-label {
  font-size: 10px;
  font-weight: 700;
  color: #6B7280;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.probabilistic-meta-value,
.metric-value {
  font-size: 14px;
  font-weight: 700;
  color: #111827;
}

.probabilistic-analytics-card {
  min-width: 0;
}

.probabilistic-analytics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.probabilistic-analytics-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  padding: 12px;
  border-radius: 6px;
  border: 1px solid #E5E7EB;
  background: #FFF;
}

.probabilistic-analytics-section.tone-neutral {
  border-color: #E5E7EB;
  background: #FFFFFF;
}

.probabilistic-analytics-section.tone-warning {
  border-color: #FCD34D;
  background: #FFFBEA;
}

.probabilistic-analytics-section.tone-success {
  border-color: #86EFAC;
  background: #F0FDF4;
}

.probabilistic-analytics-section.tone-error {
  border-color: #FDA4AF;
  background: #FFF1F2;
}

.probabilistic-analytics-header {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}

.probabilistic-analytics-headline {
  font-size: 13px;
  font-weight: 700;
  line-height: 1.5;
  color: #111827;
}

.probabilistic-analytics-body {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: #374151;
}

.probabilistic-warning-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.probabilistic-warning-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(17, 24, 39, 0.06);
  color: #374151;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.2;
}

/* Timeline Header */
.timeline-header {
  position: sticky;
  top: 0;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(8px);
  padding: 12px 24px;
  border-bottom: 1px solid #EAEAEA;
  z-index: 5;
  display: flex;
  justify-content: center;
}

.timeline-stats {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 11px;
  color: #666;
  background: #F5F5F5;
  padding: 4px 12px;
  border-radius: 20px;
}

.total-count {
  font-weight: 600;
  color: #333;
}

.platform-breakdown {
  display: flex;
  align-items: center;
  gap: 8px;
}

.breakdown-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.breakdown-divider { color: #DDD; }
.breakdown-item.twitter { color: #000; }
.breakdown-item.reddit { color: #000; }

/* --- Timeline Feed --- */
.timeline-feed {
  padding: 24px 0;
  position: relative;
  min-height: 100%;
  max-width: 900px;
  margin: 0 auto;
}

.timeline-axis {
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 1px;
  background: #EAEAEA; /* Cleaner line */
  transform: translateX(-50%);
}

.timeline-item {
  display: flex;
  justify-content: center;
  margin-bottom: 32px;
  position: relative;
  width: 100%;
}

.timeline-marker {
  position: absolute;
  left: 50%;
  top: 24px;
  width: 10px;
  height: 10px;
  background: #FFF;
  border: 1px solid #CCC;
  border-radius: 50%;
  transform: translateX(-50%);
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
}

.marker-dot {
  width: 4px;
  height: 4px;
  background: #CCC;
  border-radius: 50%;
}

.timeline-item.twitter .marker-dot { background: #000; }
.timeline-item.reddit .marker-dot { background: #000; }
.timeline-item.twitter .timeline-marker { border-color: #000; }
.timeline-item.reddit .timeline-marker { border-color: #000; }

/* Card Layout */
.timeline-card {
  width: calc(100% - 48px);
  background: #FFF;
  border-radius: 2px;
  padding: 16px 20px;
  border: 1px solid #EAEAEA;
  box-shadow: 0 2px 10px rgba(0,0,0,0.02);
  position: relative;
  transition: all 0.2s;
}

.timeline-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.05);
  border-color: #DDD;
}

/* Left side (Twitter) */
.timeline-item.twitter {
  justify-content: flex-start;
  padding-right: 50%;
}
.timeline-item.twitter .timeline-card {
  margin-left: auto;
  margin-right: 32px; /* Gap from axis */
}

/* Right side (Reddit) */
.timeline-item.reddit {
  justify-content: flex-end;
  padding-left: 50%;
}
.timeline-item.reddit .timeline-card {
  margin-right: auto;
  margin-left: 32px; /* Gap from axis */
}

/* Card Content Styles */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #F5F5F5;
}

.agent-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.avatar-placeholder {
  width: 24px;
  height: 24px;
  background: #000;
  color: #FFF;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.agent-name {
  font-size: 13px;
  font-weight: 600;
  color: #000;
}

.header-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.platform-indicator {
  color: #999;
  display: flex;
  align-items: center;
}

.action-badge {
  font-size: 9px;
  padding: 2px 6px;
  border-radius: 2px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border: 1px solid transparent;
}

/* Monochromatic Badges */
.badge-post { background: #F0F0F0; color: #333; border-color: #E0E0E0; }
.badge-comment { background: #F0F0F0; color: #666; border-color: #E0E0E0; }
.badge-action { background: #FFF; color: #666; border: 1px solid #E0E0E0; }
.badge-meta { background: #FAFAFA; color: #999; border: 1px dashed #DDD; }
.badge-idle { opacity: 0.5; }

.content-text {
  font-size: 13px;
  line-height: 1.6;
  color: #333;
  margin-bottom: 10px;
}

.content-text.main-text {
  font-size: 14px;
  color: #000;
}

/* Info Blocks (Quote, Repost, etc) */
.quoted-block, .repost-content {
  background: #F9F9F9;
  border: 1px solid #EEE;
  padding: 10px 12px;
  border-radius: 2px;
  margin-top: 8px;
  font-size: 12px;
  color: #555;
}

.quote-header, .repost-info, .like-info, .search-info, .follow-info, .vote-info, .idle-info, .comment-context {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 11px;
  color: #666;
}

.icon-small {
  color: #999;
}
.icon-small.filled {
  color: #999; /* Keep icons neutral unless highlighted */
}

.search-query {
  font-family: 'JetBrains Mono', monospace;
  background: #F0F0F0;
  padding: 0 4px;
  border-radius: 2px;
}

.card-footer {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
  font-size: 10px;
  color: #BBB;
  font-family: 'JetBrains Mono', monospace;
}

/* Waiting State */
.waiting-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  color: #CCC;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.pulse-ring {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid #EAEAEA;
  animation: ripple 2s infinite;
}

@keyframes ripple {
  0% { transform: scale(0.8); opacity: 1; border-color: #CCC; }
  100% { transform: scale(2.5); opacity: 0; border-color: #EAEAEA; }
}

/* Animation */
.timeline-item-enter-active,
.timeline-item-leave-active {
  transition: all 0.4s cubic-bezier(0.165, 0.84, 0.44, 1);
}

.timeline-item-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.timeline-item-leave-to {
  opacity: 0;
}

/* Logs */
.system-logs {
  background: #000;
  color: #DDD;
  padding: 16px;
  font-family: 'JetBrains Mono', monospace;
  border-top: 1px solid #222;
  flex-shrink: 0;
}

.log-header {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid #333;
  padding-bottom: 8px;
  margin-bottom: 8px;
  font-size: 10px;
  color: #666;
}

.log-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  height: 100px;
  overflow-y: auto;
  padding-right: 4px;
}

.log-content::-webkit-scrollbar { width: 4px; }
.log-content::-webkit-scrollbar-thumb { background: #333; border-radius: 2px; }

.log-line {
  font-size: 11px;
  display: flex;
  gap: 12px;
  line-height: 1.5;
}

.log-time { color: #555; min-width: 75px; }
.log-msg { color: #BBB; word-break: break-all; }
.mono { font-family: 'JetBrains Mono', monospace; }

/* Loading spinner for button */
.loading-spinner-small {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #FFF;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-right: 6px;
}
</style>
