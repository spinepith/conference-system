using System.Net.Http.Headers;
using System.Net.Http.Json;

namespace ContentValidation.Core;


file record OpenAiRequest(string Model, object[] Messages, double Temperature, object ResponseFormat);
file record OpenAiResponse(Choice[] Choices);
file record Choice(Message Message);
file record Message(string Role, string Content);

public class LlmService : ILlmProvider {
    private readonly HttpClient httpClient;
    private readonly string modelName;

    public LlmService(string apiKey, string baseUrl = "https://api.openai.com/v1/", string modelName = "gpt-4o-mini") {
        httpClient = new HttpClient { BaseAddress = new Uri(baseUrl) };
        httpClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", apiKey);
        this.modelName = modelName;
    }

    public async Task<string> GetResponseAsync(string systemPrompt, string userText) {
        var request = new OpenAiRequest(
            Model: modelName,
            Messages: new object[] {
                new { role = "system", content = systemPrompt },
                new { role = "user", content = userText }
            },
            Temperature: 0.1,
            ResponseFormat: new { type = "json_object" }
        );

        var response = await httpClient.PostAsJsonAsync("chat/completions", request);

        if (!response.IsSuccessStatusCode) {
            var error = await response.Content.ReadAsStringAsync();
            throw new Exception($"LLM API Error: {response.StatusCode} - {error}");
        }

        var responseData = await response.Content.ReadFromJsonAsync<OpenAiResponse>();

        return responseData?.Choices?[0].Message.Content ?? "{}";
    }
}
