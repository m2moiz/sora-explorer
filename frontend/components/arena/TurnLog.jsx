export default function TurnLog({ turns, winnerName }) {
  return (
    <section className="turn-log">
      <div className="panel-title">
        <span>Turn Log</span>
        {winnerName ? <strong>{winnerName} wins</strong> : <strong>Ready</strong>}
      </div>
      <div className="turn-list">
        {turns.length === 0 ? (
          <p className="quiet">Create two creatures and start the battle.</p>
        ) : (
          turns.map((turn) => (
            <article key={turn.turn} className="turn-item">
              <span>{turn.turn}</span>
              <p>
                <strong>{turn.attackerName}</strong> used {turn.move} for {turn.damage} damage.
                <em>{turn.modifier}</em>
              </p>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
