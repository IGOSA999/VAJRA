# Web integration note

The deployed dashboard originally showed empty output after a solver request failed without a useful client message. The release now uses a health gate, non-empty HTTP error handling, structured request timing logs and a spawned background worker for interactive computation.
