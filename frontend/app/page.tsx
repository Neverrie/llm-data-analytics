import { LabCard } from "../components/LabCard";
import { SectionCard } from "../components/SectionCard";

export default function HomePage() {
  return (
    <div className="space-y-6">
      <section className="neu-card p-7">
        <h1 className="text-3xl font-bold tracking-tight app-text">LLM Data Analyst Lab</h1>
        <p className="mt-3 max-w-3xl text-sm muted-text md:text-base">
          Учебный проект по дисциплине «LLM как инструмент аналитика данных». Интерфейс содержит каркас для трёх лабораторных работ и backend API для дальнейшего развития.
        </p>
      </section>

      <SectionCard title="Статус проекта">
        <p>
          Репозиторий и базовая архитектура готовы. Реальная аналитика, работа с CSV и интеграция с локальной LLM через Ollama будут добавлены на следующих этапах.
        </p>
      </SectionCard>

      <section className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
        <LabCard
          href="/lab1"
          number="Lab 1"
          title="Prompt Engineering EDA"
          goal="Проработать EDA через серию промптов, ответы LLM и комментарии аналитика."
          maxScore={35}
          status="Каркас готов"
        />
        <LabCard
          href="/lab2"
          number="Lab 2"
          title="API Pipeline"
          goal="Собрать конвейер CSV → prompt → LLM → JSON и сохранить структуру результата."
          maxScore={30}
          status="В разработке"
        />
        <LabCard
          href="/lab3"
          number="Lab 3"
          title="LLM Analytics Agent"
          goal="Подготовить мини-продукт с агентом, tools и защитами для аналитических запросов."
          maxScore={35}
          status="В разработке"
        />
      </section>
    </div>
  );
}
