using System.Text.Json.Serialization;


namespace ContentValidation.Models;

public class CheckResult {
    [JsonPropertyName("check_id")]
    public string? CheckId                         { get; set; }
                                                     
    [JsonPropertyName("title")]                      
    public string? Title                           { get; set; }
                                                     
    [JsonPropertyName("status")]                     
    public string? Status                          { get; set; }
                                                     
    [JsonPropertyName("risk_level")]                 
    public string? RiskLevel                       { get; set; }
                                                     
    [JsonPropertyName("score")]                      
    public double? Score                           { get; set; }
                                                     
    [JsonPropertyName("summary")]                    
    public string? Summary                         { get; set; }
                                                     
    [JsonPropertyName("warnings")]                   
    public List<CheckIssue>? Warnings              { get; set; }
                                                     
    [JsonPropertyName("errors")]                     
    public List<CheckIssue>? Errors                { get; set; }

    [JsonPropertyName("flagged_fragments")]
    public List<FlaggedFragment>? FlaggedFragments { get; set; }

    [JsonPropertyName("author_comment")]
    public string? AuthorComment                   { get; set; }
                                                     
    [JsonPropertyName("editor_comment")]             
    public string? EditorComment                   { get; set; }

    [JsonPropertyName("raw_model_response")]
    public RawModelResponseData? RawModelResponse  { get; set; }

    public class CheckIssue {
        [JsonPropertyName("code")]
        public string? Code           { get; set; }

        [JsonPropertyName("message")]
        public string? Message        { get; set; }

        [JsonPropertyName("location")]
        public string? Location       { get; set; }

        [JsonPropertyName("recommendation")]
        public string? Recommendation { get; set; }
    }

    public class FlaggedFragment {
        [JsonPropertyName("fragment")]
        public string? Fragment       { get; set; }

        [JsonPropertyName("risk_type")]
        public string? RiskType       { get; set; }

        [JsonPropertyName("reason")]
        public string? Reason         { get; set; }

        [JsonPropertyName("recommendation")]
        public string? Recommendation { get; set; }
    }

    public class RawModelResponseData {
        [JsonPropertyName("model")]
        public string? Model     { get; set; }

        [JsonPropertyName("timestamp")]
        public string? Timestamp { get; set; }

        [JsonPropertyName("response")]
        public string? Response  { get; set; }
    }
}
