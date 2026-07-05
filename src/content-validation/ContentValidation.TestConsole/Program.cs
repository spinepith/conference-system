using ContentValidation.Core;


namespace ContentValidation.TestConsole;

internal class Program {
    private static async Task Main(string[] args) {
        ILlmProvider llmProvider = new LlmService("");

        string prompt = "Ты дружелюбный ассистент-проверяющий. Просто поздоровайся с пользователем.";
        string text = "Здарова";

        string result = await llmProvider.GetResponseAsync(prompt, text);
        Console.WriteLine($"Ответ: {result}");
    }
}