"use client";

export function EmptyChatState({ datasetName, onPrompt }: { datasetName?: string; onPrompt: (text: string) => void }) {
  const prompts = [
    "Сделай краткий обзор датасета: строки, колонки и пропуски.",
    "Покажи ключевые корреляции между числовыми признаками.",
    "Найди аномалии, дубликаты и возможные проблемы в данных.",
    "Построй базовые графики распределений по важным колонкам."
  ];

  return (
    <div className="empty-chat-state">
      <h3>Новый чат</h3>
      <p>Выберите датасет и отправьте запрос.</p>
      {datasetName ? <div className="dataset-pill">Dataset: {datasetName}</div> : null}
      <div className="prompt-grid">
        {prompts.map((prompt) => (
          <button key={prompt} className="prompt-chip" onClick={() => onPrompt(prompt)}>{prompt}</button>
        ))}
      </div>
    </div>
  );
}
