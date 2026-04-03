# Planned Build Phases

## Phase 0: Scaffold

- create the monorepo layout
- set up backend and frontend skeletons
- add environment, Docker, and documentation scaffolding

## Phase 1: Data Foundation

- ingest the raw H&M data from `data/raw/`
- create cleaned and intermediate datasets
- document the main entities and joins
- establish offline split strategy

## Phase 2: Candidate Retrieval

- build collaborative retrieval
- build content retrieval
- add search retrieval
- add session retrieval
- track retrieval metrics separately

## Phase 3: Blending and Reranking

- combine retrieval outputs into one candidate pool
- add a first reranking layer
- introduce explanation features where useful
- compare approaches with offline evaluation

## Phase 4: Product Experience

- connect backend APIs to the frontend
- add home feed and product detail surfaces
- support similar items and likes/saves
- expose search plus recommendation blending in the UI

## Phase 5: Experimentation and Operations

- add experiment tracking
- add model/index versioning
- formalize artifact promotion
- prepare the project for repeatable iteration

TODO: keep each phase independently runnable and easy to inspect.
