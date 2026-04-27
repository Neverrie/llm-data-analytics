import { LabCard } from "../components/LabCard";
import { SectionCard } from "../components/SectionCard";

export default function HomePage() {
  return (
    <div className="space-y-6">
      <section className="app-card p-6">
        <h1 className="mb-2 text-3xl font-bold tracking-tight">LLM Data Analyst Lab</h1>
        <p className="max-w-4xl text-sm app-muted md:text-base">
          Учебный проект по дисциплине «LLM как инструмент аналитика данных». Интерфейс содержит каркас для трёх лабораторных работ и backend API-заглушки для развития проекта.
        </p>
      </section>

      <SectionCard title="Статус проекта">
        <p>Базовая архитектура готова. В следующих этапах будет добавляться реальная аналитика, работа с CSV и расширение LLM-логики.</p>
      </SectionCard>

      <section className="app-grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
        <LabCard
          href="/lab1"
          number="Lab 1"
          title="Prompt Engineering EDA"
          goal="EDA через серию промптов, ответы LLM и комментарии аналитика."
          maxScore={35}
          status="Каркас готов"
        />
        <LabCard
          href="/lab2"
          number="Lab 2"
          title="API Pipeline"
          goal="Конвейер CSV → prompt → LLM → JSON и сохранение результата."
          maxScore={30}
          status="В разработке"
        />
        <LabCard
          href="/lab3"
          number="Lab 3"
          title="LLM Analytics Agent"
          goal="Мини-продукт с агентом, tools и безопасной аналитикой."
          maxScore={35}
          status="В разработке"
        />
      </section>
    </div>
  );
}
