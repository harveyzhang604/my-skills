/**
 * Story-Guided Free Talk prompt helpers.
 *
 * This file is intentionally framework-neutral. It does not call the local
 * voice runtime directly; the app can import/copy these types and prompt
 * builders when wiring missions into conversation-runtime customDesc.
 */

export type ConversationBeat = {
  id: string;
  label: string;
  label_zh?: string;
  intent: string;
  acceptance_criteria: string;
  example_phrases?: string[];
  source_dialogue_indices?: number[];
};

export type ConversationMission = {
  page: number;
  chapter: number;
  scene: string;
  characters: string[];
  user_role: string;
  ai_role: string;
  mission_summary: string;
  must_hit_beats: ConversationBeat[];
  target_phrases: string[];
  vocabulary_focus?: string[];
  estimated_turns?: number;
  language_level?: string;
  success_rule?: string;
  coach_note?: string;
};

export type DirectorAnalysis = {
  current_beat: string;
  user_intent: string;
  beat_completed: boolean;
  next_beat: string | null;
  needs_hint: boolean;
  off_track: boolean;
  guidance: 'continue' | 'redirect' | 'hint' | 'encourage' | string;
  progress: string;
  confidence?: number;
  reason?: string;
  llm_error?: string;
};

export type StoryGuidedTurn = {
  userText: string;
  userTextZh?: string;
  mission: ConversationMission;
  analysis?: Partial<DirectorAnalysis>;
  history?: Array<{
    role: 'user' | 'assistant' | 'ai';
    text: string;
  }>;
};

export type StoryGuidedReplyAdapter = {
  generateReply(input: {
    customDesc: string;
    userText: string;
    history: StoryGuidedTurn['history'];
    mission: ConversationMission;
    analysis?: Partial<DirectorAnalysis>;
  }): Promise<string>;
};

export type StoryGuidedUIState = {
  currentPage: number;
  currentChapter: number;
  sceneImage: string;
  mission: {
    scene: string;
    userRole: string;
    aiRole: string;
    missionSummary: string;
  };
  progress: {
    totalBeats: number;
    completedBeats: number;
    currentBeat: string | null;
    progressPercentage: number;
    completed: boolean;
  };
  hints: {
    targetPhrases: string[];
    currentHint?: string;
  };
};

export function buildStoryGuidedCustomDesc(
  mission: ConversationMission,
  analysis?: Partial<DirectorAnalysis>
): string {
  const currentBeat =
    analysis?.current_beat || mission.must_hit_beats[0]?.label || 'Start the scene';
  const nextBeat = analysis?.next_beat || 'Continue the scene naturally';
  const progress = analysis?.progress || `0/${mission.must_hit_beats.length}`;
  const guidance = analysis?.guidance || 'encourage';

  return [
    `Story-Guided Free Talk scene: ${mission.scene}`,
    `AI role: ${mission.ai_role}`,
    `Learner role: ${mission.user_role}`,
    `Mission: ${mission.mission_summary}`,
    `Progress: ${progress}`,
    '',
    'Hidden story beats:',
    ...mission.must_hit_beats.map((beat, index) => {
      const examples = (beat.example_phrases || []).slice(0, 1).join(' / ');
      return `${index + 1}. ${beat.label}${beat.label_zh ? ` (${beat.label_zh})` : ''}; success: ${beat.acceptance_criteria}${examples ? `; example: ${examples}` : ''}`;
    }),
    '',
    `Current beat: ${currentBeat}`,
    `Next beat: ${nextBeat}`,
    `Director guidance: ${guidance}`,
    '',
    'Conversation rules:',
    '- Reply as the AI role in English only.',
    '- Keep replies under 20 words.',
    '- End with one natural question or prompt.',
    '- Do not force exact lines; accept any natural expression that completes the beat.',
    '- If the learner is off track, acknowledge briefly and guide back to the current beat.',
    '- If the learner is stuck, give a gentle hint using one target phrase.',
    '',
    'Target phrases learners may use:',
    ...mission.target_phrases.slice(0, 6).map((phrase) => `- ${phrase}`),
  ].join('\n');
}

export function buildStoryGuidedTurnInput(turn: StoryGuidedTurn): {
  customDesc: string;
  userText: string;
  history: StoryGuidedTurn['history'];
  mission: ConversationMission;
  analysis?: Partial<DirectorAnalysis>;
} {
  return {
    customDesc: buildStoryGuidedCustomDesc(turn.mission, turn.analysis),
    userText: turn.userText,
    history: turn.history || [],
    mission: turn.mission,
    analysis: turn.analysis,
  };
}

export async function generateStoryGuidedReply(
  adapter: StoryGuidedReplyAdapter,
  turn: StoryGuidedTurn
): Promise<string> {
  return adapter.generateReply(buildStoryGuidedTurnInput(turn));
}

export function buildStoryGuidedInitialState(
  mission: ConversationMission,
  sceneImage: string
): StoryGuidedUIState {
  return {
    currentPage: mission.page,
    currentChapter: mission.chapter,
    sceneImage,
    mission: {
      scene: mission.scene,
      userRole: mission.user_role,
      aiRole: mission.ai_role,
      missionSummary: mission.mission_summary,
    },
    progress: {
      totalBeats: mission.must_hit_beats.length,
      completedBeats: 0,
      currentBeat: mission.must_hit_beats[0]?.label || null,
      progressPercentage: 0,
      completed: mission.must_hit_beats.length === 0,
    },
    hints: {
      targetPhrases: mission.target_phrases,
    },
  };
}
