export type CreatureStats = {
  hp: number;
  atk: number;
  def: number;
  speed: number;
  magic: number;
};

export type ProviderStatus = {
  provider: string;
  mode: string;
  modelId?: string | null;
  status?: string;
};

export type Creature = {
  id: string;
  name: string;
  description: string;
  element: string;
  archetype: string;
  rarity: string;
  stats: CreatureStats;
  abilities: string[];
  weaknesses: string[];
  visualUrl: string;
  visualGradient: string;
  providerStatus: ProviderStatus;
  rawExtraction: Record<string, unknown>;
  latencyMs: number;
  fallback: boolean;
};

export type BattleTurn = {
  turn: number;
  attackerId: string;
  attackerName: string;
  defenderId: string;
  defenderName: string;
  move: string;
  damage: number;
  modifier: string;
  leftHp: number;
  rightHp: number;
};

export type BattleResult = {
  left: Creature;
  right: Creature;
  turns: BattleTurn[];
  winnerId: string;
  winnerName: string;
  finalHp: Record<string, number>;
};

export const samplePrompts = [
  "a glass phoenix that reflects spells but shatters under thunder",
  "a thunder golem with copper veins and storm fists",
  "a moss vampire blooming in a moonlit crypt",
  "a clockwork basilisk with ticking brass eyes",
  "a mirror kraken that copies enemy attacks from the abyss"
];
