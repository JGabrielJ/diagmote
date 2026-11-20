Feature: Monitoramento do sistema
    Como técnico de suporte
    Quero que o agente colete informações do computador
    Para acompanhar suas condições de funcionamento

    Scenario: Coletar e armazenar métricas do computador
        Given que o agente de monitoramento está configurado
        When um ciclo de coleta de métricas é executado
        Then as métricas do sistema devem ser coletadas
        And os dados devem ser armazenados em um arquivo CSV
