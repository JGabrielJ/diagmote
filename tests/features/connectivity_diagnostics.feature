Feature: Diagnóstico de conectividade
  Como técnico de suporte
  Quero identificar falhas de conectividade
  Para registrar problemas de comunicação com a rede

  Scenario: Registrar uma falha de conectividade
    Given que o diagnóstico de conectividade está configurado
    When uma verificação de conectividade falha
    Then o resultado deve indicar uma falha
    And a falha deve ser registrada em um arquivo CSV
