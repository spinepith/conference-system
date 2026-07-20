using GenerativeAI;
using GenerativeAI.Types;


namespace ContentValidation.Core;

public class LlmClient {
    private readonly GenerativeModel _model;

    public LlmClient(string apiKey, string model) {
        var config = new GenerationConfig {
            Temperature      = 0.2f,
            MaxOutputTokens  = 2048,
            TopP             = 0.95f,
            ResponseMimeType = "application/json"
        };
        
        _model = new GenerativeModel(apiKey, model, config);
    }

    public async Task<string> SendRequestAsync(string systemPrompt, string userMessage) {
        try {
            string prompt = $"{systemPrompt}\n\nТекст для проверки:\n{userMessage}";
            return (await _model.GenerateContentAsync(prompt)).Text ?? string.Empty;
        }
        catch (Exception ex) { return ex.Message; }
    }
}
