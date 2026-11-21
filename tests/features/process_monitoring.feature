Feature: Monitoramento de processos
  Como técnico de suporte
  Quero acompanhar os processos em execução
  Para identificar o consumo de recursos do computador

  Scenario: Coletar e armazenar informações dos processos
    Given que o agente de monitoramento está configurado
    When as informações dos processos em execução são coletadas
    Then a coleta deve retornar uma lista de processos
    And as informações dos processos disponíveis devem ser armazenadas em um arquivo CSV
