---
title: PawPal+ UML Class Diagram
---

```mermaid
classDiagram
    class Owner {
        +String id
        +String name
        +Dict pets
        +add_pet(pet) None
        +edit_pet(pet_id, kwargs) None
        +delete_pet(pet_id) None
    }

    class Pet {
        +String id
        +String name
        +date birthday
        +String sex
        +String species
        +List allergies
        +List tasks
        +edit_name(new_name) None
        +edit_sex(new_sex) None
        +edit_species(new_species) None
        +edit_birthday(new_birthday) None
        +add_task(task_id) None
        +remove_task(task_id) None
    }

    class Task {
        +String id
        +String title
        +datetime scheduled_at
        +String description
        +bool reminder
        +bool repeated
        +String recurrence
        +int priority
        +bool completed
        +String owner_id
        +List pet_ids
        +mark_complete() Task
    }

    class Scheduler {
        +Dict tasks_by_id
        +Dict tasks_by_date
        +Dict tasks_by_pet
        +create_task(title, scheduled_at, owner_id, pet_ids) Task
        +add_task(task) None
        +edit_task(task_id, kwargs) None
        +delete_task(task_id) None
        +assign_task_to_pets(task_id, pet_ids, pet_store) None
        +unassign_task_from_pet(task_id, pet_id, pet_store) None
        +view_tasks_on(target_date) List
        +view_future_tasks(from_date) List
        +sort_by_time(tasks) List
        +check_conflicts(tasks, pet_store) List
        +filter_tasks(tasks, completed, pet_name, pet_store) List
    }

    class PawPalBot {
        +String docs_folder
        +GeminiClient llm_client
        +List owners
        +Scheduler scheduler
        +List pets
        +List documents
        +List paragraphs
        +Dict index
        +int min_evidence_score
        +float min_evidence_coverage
        +reload() PawPalBot
        +set_pawpal_data(owners, scheduler, pets) PawPalBot
        +load_documents() List
        +build_index(paragraphs) Dict
        +retrieve(query, top_k) List
        +retrieve_with_scores(query, top_k) List
        +has_meaningful_evidence(query, scored) bool
        +answer_retrieval_only(query, top_k) String
        +answer_rag(query, top_k) String
        +suggest_task(query, top_k) Dict
        +full_corpus_text() String
    }

    class GeminiClient {
        +Client client
        +naive_answer_over_full_docs(query, all_text) String
        +answer_from_snippets(query, snippets) String
        +suggest_task(query, snippets) Dict
    }

    class pawpal_context {
        <<module>>
        +build_pawpal_documents(owners, scheduler, pets) List
        +build_pet_store(owners) Dict
    }

    %% Owner holds Pet objects in its pets dict
    Owner "1" *-- "*" Pet : owns

    %% Pet.owner is set back by Owner.add_pet()
    Pet "*" --> "1" Owner : owner (back-ref)

    %% Scheduler is the authoritative store of Task objects
    Scheduler "1" *-- "*" Task : manages

    %% Pet stores task IDs only (no Task objects)
    Pet "1" ..> "*" Task : references by task_id

    %% Task stores owner_id and pet_ids (string references, not objects)
    Task "*" ..> "0..1" Owner : owner_id
    Task "*" ..> "*" Pet : pet_ids

    %% RAG assistant layer over the live PawPal data
    PawPalBot "1" o-- "0..1" GeminiClient : llm_client (optional)
    PawPalBot ..> pawpal_context : builds documents
    PawPalBot ..> Owner : reads live data
    PawPalBot ..> Scheduler : reads live data
    PawPalBot ..> Pet : reads live data

    %% Bridge serializes PawPal objects into (filename, text) documents
    pawpal_context ..> Owner : serializes
    pawpal_context ..> Pet : serializes
    pawpal_context ..> Scheduler : serializes

    %% GeminiClient generates answers/suggestions from retrieved snippets
    PawPalBot ..> GeminiClient : answer_from_snippets / suggest_task
```
