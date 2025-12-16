# System Architecture

The Gemscap Pro Terminal follows a modular microservices-like architecture designed for scalability and separation of concerns.

```mermaid
graph TD
    %% Nodes
    EXT["Binance Futures API"]
    
    subgraph "Backend Services"
        INGEST["Ingestion Service<br/>(src/ingestion)"]
        STORE[("Redis / Data Buffer")]
        ANALYTICS["Analytics Engine<br/>(src/analytics)"]
    end
    
    subgraph "Frontend"
        UI["Streamlit Dashboard<br/>(src/dashboard)"]
        USER(("Quant Trader"))
    end

    %% Edge Connections
    EXT -->|"WSS / REST Stream"| INGEST
    INGEST -->|"Normalize & buffer ticks"| STORE
    
    STORE -->|"Fetch Rolling Window"| ANALYTICS
    ANALYTICS -->|"Compute Z-Score/OLS"| STORE
    
    STORE -->|"Poll Processed Data"| UI
    UI -->|"Visuals & Alerts"| USER
    
    %% Styling
    style EXT fill:#f9f,stroke:#333,stroke-width:2px
    style STORE fill:#ff9,stroke:#333,stroke-width:2px
    style UI fill:#9cf,stroke:#333,stroke-width:2px