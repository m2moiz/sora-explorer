"use client";

const LANGUAGE_FLAGS = {
  "es-ES": "🇪🇸",
  "es": "🇪🇸",
  "fr-FR": "🇫🇷",
  "fr": "🇫🇷",
  "de-DE": "🇩🇪",
  "de": "🇩🇪",
  "ja-JP": "🇯🇵",
  "ja": "🇯🇵",
  "zh-CN": "🇨🇳",
  "zh": "🇨🇳",
};

export default function PhrasePrompt({ room, onPlayExample }) {
  if (!room) return null;

  const flag = LANGUAGE_FLAGS[room.language] || "🌐";
  const phonetic = room.phonetic;

  return (
    <div className="phrase-prompt">
      <div className="phrase-prompt__header">
        <span className="phrase-prompt__flag" aria-label={room.language}>{flag}</span>
        <span className="phrase-prompt__lang">{room.language}</span>
      </div>

      <p className="phrase-prompt__target" lang={room.language}>
        {room.targetPhrase}
      </p>

      {room.translation && (
        <p className="phrase-prompt__translation">
          {room.translation}
        </p>
      )}

      {phonetic && (
        <p className="phrase-prompt__phonetic">
          <span className="phrase-prompt__phonetic-label">How to say it: </span>
          <em>{phonetic}</em>
        </p>
      )}

      <button
        type="button"
        className="phrase-prompt__play"
        onClick={onPlayExample}
        aria-label="Play example pronunciation"
      >
        ▶ Play Example
      </button>
    </div>
  );
}
