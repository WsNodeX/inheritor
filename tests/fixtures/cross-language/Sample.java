public class Sample {
    // A string containing a line-comment marker. Must not be read as a comment.
    private static final String BASE = "http://example.com/api/v2";

    // A string containing a block-comment opener and closer. Same reason.
    private static final String NOTE = "/* planned, not shipped */";

    // TODO: retry the upload on a transient failure
    public void noExitCondition() {
    }

    // TODO: delete this shim once the v2 endpoint is in production (2026-Q2)
    public void hasExitCondition() {
    }

    /* FIXME: nobody owns this branch */
    public void blockComment() {
    }

    /* TODO: replace with the streaming API once it leaves beta (#1180) */
    public void blockWithIssueRef() {
    }

    public void stringIsNotAComment() {
        // TODO: this one is real
        System.out.println("TODO: but this is just a printed string");
    }
}
