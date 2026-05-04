"use client";

export function EmptyChatState({ datasetName, onPrompt }: { datasetName?: string; onPrompt: (text: string) => void }) {
  const prompts = [
    "Сделай краткий обзор датасета: строки, колонки, пропуски и 3 главных наблюдения.",
    "Найди числовые колонки, выбери возможную целевую переменную и посчитай корреляции.",
    "Построй графики распределений для ключевых числовых колонок.",
    "Найди пропуски, дубликаты и потенциальные аномалии.",
    "Построй простую модель/регрессию, если это уместно, и объясни признаки."
  ];

  return (
    <div className="empty-chat-state">
      <h3>Новый анализ</h3>
      <p>Выберите датасет, затем вставьте готовый промпт или напишите свой запрос.</p>
      {datasetName ? <div className="dataset-pill">Dataset: {datasetName}</div> : null}
      <div className="prompt-grid">
        {prompts.map((prompt) => (
          <button key={prompt} className="prompt-chip" onClick={() => onPrompt(prompt)}>{prompt}</button>
        ))}
      </div>
    </div>
  );
}
