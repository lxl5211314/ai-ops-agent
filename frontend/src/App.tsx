import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import ChatPage from "./pages/ChatPage";
import KbPage from "./pages/KbPage";
import ProjectsPage from "./pages/ProjectsPage";
import BugAnalysisPage from "./pages/BugAnalysisPage";

export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">小龙 · 智能运维助手</div>
        <nav>
          <NavLink to="/chat">对话问答</NavLink>
          <NavLink to="/kb">知识库</NavLink>
          <NavLink to="/projects">项目源码</NavLink>
          <NavLink to="/analysis">Bug 分析</NavLink>
        </nav>
      </header>
      <main className="content">
        <Routes>
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/kb" element={<KbPage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/analysis" element={<BugAnalysisPage />} />
        </Routes>
      </main>
    </div>
  );
}
