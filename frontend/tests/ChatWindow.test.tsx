import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ChatWindow from "../src/components/ChatWindow";

describe("ChatWindow", () => {
  it("renders empty state guidance", () => {
    render(<ChatWindow messages={[]} />);
    expect(screen.getByTestId("chat-empty")).toBeInTheDocument();
  });

  it("renders user and assistant messages with citations", () => {
    render(
      <ChatWindow
        messages={[
          { id: "1", role: "user", content: "磁盘满了怎么办" },
          {
            id: "2",
            role: "assistant",
            content: "原因分析：日志堆积\n解决方案：清理日志",
            sources: [{ title: "磁盘清理手册", category: "ops_knowledge", snippet: "清理日志" }],
          },
        ]}
      />,
    );
    expect(screen.getByText("磁盘满了怎么办")).toBeInTheDocument();
    expect(screen.getByText(/原因分析/)).toBeInTheDocument();
    expect(screen.getByText("磁盘清理手册")).toBeInTheDocument();
  });

  it("shows streaming placeholder while streaming", () => {
    render(<ChatWindow messages={[{ id: "1", role: "assistant", content: "", streaming: true }]} />);
    expect(screen.getByText("…")).toBeInTheDocument();
  });
});
