```mermaid
graph LR
    %% Définition des Acteurs
    User((Voyageur))
    Notif([Système Email/Notif])
    API([Banque / API Change])

    subgraph ShareTrip_Platform [ShareTrip Platform]
        UC1([Créer un Voyage<br/>Base Currency: JPY])
        UC2([Ajouter une Dépense<br/>Adapter Pattern])
        UC3([Répartir la Dépense<br/>Strategy Pattern])
        UC4([Consulter les Équilibres<br/>Settlement])
        UC5([Recevoir Alerte Budget<br/>Notification])
        UC6([Exporter Bilan PDF<br/>Partage])

        %% Relations internes
        UC2 -.->|include| UC3
        UC3 -.->|trigger| UC5
        UC4 -.->|extend| UC6
    end

    %% Relations Acteurs
    User --- UC1
    User --- UC2
    User --- UC4
    User --- UC6

    UC2 --- API
    UC5 --- Notif

    %% Notes (simulées par des styles)
    Note5[Pattern Observer:<br/>Déclenché selon seuil]
    Note6[Génère un rapport<br/>avec graphiques]

    UC5 --- Note5
    UC6 --- Note6

    %% Style
    style Note5 fill:#fff9c4,stroke:#fbc02d,stroke-dasharray: 5 5
    style Note6 fill:#fff9c4,stroke:#fbc02d,stroke-dasharray: 5 5
    style ShareTrip_Platform fill:none,stroke:#333,stroke-width:2px
    ```
