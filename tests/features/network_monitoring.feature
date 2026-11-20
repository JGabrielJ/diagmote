Feature: Monitoramento de rede
    Como técnico de suporte
    Quero acompanhar as interfaces de rede do computador
    Para verificar suas condições e o tráfego de dados

    Scenario: Coletar e armazenar informações das interfaces de rede
        Given que o agente de monitoramento está configurado
        When as informações das interfaces de rede são coletadas
        Then a coleta deve retornar uma lista de interfaces de rede
        And os dados das interfaces disponíveis devem ser armazenados em um arquivo CSV
