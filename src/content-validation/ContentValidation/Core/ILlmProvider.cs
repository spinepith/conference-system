namespace ContentValidation.Core; 

public interface ILlmProvider {
    Task<string> GetResponseAsync(string prompt, string text);
}
