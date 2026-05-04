"use client";

export function EmptyChatState({ datasetName, onPrompt }: { datasetName?: string; onPrompt: (text: string) => void }) {
  const prompts = [
    "Сделай краткий обзор датасета",
    "Найди пропуски и аномалии",
    "Построй график распределения score",
    "Посчитай корреляции"
  ];

  return (
    <div className="empty-chat-state">
      <h3>Новый анализ</h3>
      <p>Выберите датасет и задайте вопрос.</p>
      {datasetName ? <div className="dataset-pill">Dataset: {datasetName}</div> : null}
      <div className="prompt-grid">
        {prompts.map((prompt) => (
          <button key={prompt} className="prompt-chip" onClick={() => onPrompt(prompt)}>{prompt}</button>
        ))}
      </div>
    </div>
  );
}
