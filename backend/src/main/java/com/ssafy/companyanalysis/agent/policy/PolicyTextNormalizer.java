package com.ssafy.companyanalysis.agent.policy;

import java.text.Normalizer;
import java.util.regex.Pattern;
import org.springframework.stereotype.Component;

@Component
public final class PolicyTextNormalizer {

    private static final Pattern INVISIBLE = Pattern.compile(
            "[\\u200B-\\u200F\\u202A-\\u202E\\u2060\\u2066-\\u2069\\uFEFF]");
    private static final Pattern CONTROL = Pattern.compile("[\\p{Cc}&&[^\\r\\n\\t]]");
    private static final Pattern WHITESPACE = Pattern.compile("\\s+");
    private static final Pattern EXTREME_REPETITION = Pattern.compile("(.)\\1{11,}");

    public NormalizedText normalize(String rawText) {
        String original = rawText == null ? "" : rawText;
        String compatibility = Normalizer.normalize(original, Normalizer.Form.NFKC);
        boolean hidden = INVISIBLE.matcher(compatibility).find()
                || CONTROL.matcher(compatibility).find();
        String visible = INVISIBLE.matcher(compatibility).replaceAll("");
        visible = CONTROL.matcher(visible).replaceAll("");
        visible = WHITESPACE.matcher(visible).replaceAll(" ").trim();
        boolean suspicious = hidden || EXTREME_REPETITION.matcher(visible).find();
        return new NormalizedText(original, visible, suspicious);
    }
}
