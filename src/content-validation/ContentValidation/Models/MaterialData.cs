using System.Text.Json.Serialization;


namespace ContentValidation.Models;

public class MaterialData {
    [JsonPropertyName("title")]
    public string? Title                  { get; set; }

    [JsonPropertyName("authors")]
    public List<string>? Authors          { get; set; }

    [JsonPropertyName("organization")]
    public string? Organization           { get; set; }

    [JsonPropertyName("abstract")]
    public string? Abstract               { get; set; }

    [JsonPropertyName("keywords")]
    public List<string>? Keywords         { get; set; }

    [JsonPropertyName("body_text")]
    public string? BodyText               { get; set; }

    [JsonPropertyName("sections")]
    public List<SectionData>? Sections    { get; set; }

    [JsonPropertyName("references")]
    public List<string>? References       { get; set; }

    [JsonPropertyName("objects")]
    public DocumentObjects? Objects       { get; set; }

    [JsonPropertyName("warnings")]
    public List<string>? Warnings         { get; set; }

    [JsonPropertyName("udc")]
    public string? Udc                    { get; set; }

    [JsonPropertyName("title_en")]
    public string? TitleEn                { get; set; }

    [JsonPropertyName("authors_en")]
    public List<string>? AuthorsEn        { get; set; }

    [JsonPropertyName("organization_en")]
    public string? OrganizationEn         { get; set; }

    [JsonPropertyName("email")]
    public string? Email                  { get; set; }

    [JsonPropertyName("supervisor")]
    public string? Supervisor             { get; set; }

    [JsonPropertyName("abstract_en")]
    public string? AbstractEn             { get; set; }

    [JsonPropertyName("keywords_en")]
    public List<string>? KeywordsEn       { get; set; }

    public class SectionData {
        [JsonPropertyName("title")]
        public string? Title { get; set; }

        [JsonPropertyName("text")]
        public string? Text  { get; set; }
    }

    public class DocumentObjects {
        [JsonPropertyName("tables_count")]
        public int TablesCount    { get; set; }

        [JsonPropertyName("figures_count")]
        public int FiguresCount   { get; set; }

        [JsonPropertyName("equations_count")]
        public int EquationsCount { get; set; }
    }
}
