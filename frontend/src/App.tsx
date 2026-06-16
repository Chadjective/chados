import { useRef } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import SearchBar from './components/SearchBar';
import EmailList from './components/EmailList';
import EmailView from './components/EmailView';
import ThreadView from './components/ThreadView';
import PhotoTimeline from './components/PhotoTimeline';
import AlbumGrid from './components/AlbumGrid';
import ContactList from './components/ContactList';
import CalendarView from './components/CalendarView';
import ChatView from './components/ChatView';
import DriveView from './components/DriveView';
import NotesView from './components/NotesView';
import GlobalSearch from './components/GlobalSearch';
import AnalyticsDashboard from './components/AnalyticsDashboard';
import AIChat from './components/AIChat';
import TrashView from './components/TrashView';
import SpaceManager from './components/SpaceManager';
import TagManager from './components/TagManager';
import PhotoImport from './components/PhotoImport';
import './App.css';

function AppLayout() {
  const searchInputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="app">
      <Sidebar />
      <div className="main-content">
        <SearchBar ref={searchInputRef} />
        <div className="content-area">
          <Routes>
            <Route
              path="/"
              element={<EmailList searchInputRef={searchInputRef} />}
            />
            <Route
              path="/label/:name"
              element={<EmailList searchInputRef={searchInputRef} />}
            />
            <Route
              path="/search"
              element={<EmailList searchInputRef={searchInputRef} />}
            />
            <Route path="/email/:id" element={<EmailView />} />
            <Route path="/thread/:id" element={<ThreadView />} />
            <Route path="/photos" element={<PhotoTimeline />} />
            <Route path="/photos/videos" element={<PhotoTimeline />} />
            <Route path="/photos/favorites" element={<PhotoTimeline />} />
            <Route path="/photos/search" element={<PhotoTimeline />} />
            <Route path="/photos/album/:albumId" element={<PhotoTimeline />} />
            <Route path="/photos/albums" element={<AlbumGrid />} />
            <Route path="/photos/import" element={<PhotoImport />} />
            <Route path="/contacts" element={<ContactList />} />
            <Route path="/contacts/:id" element={<ContactList />} />
            <Route path="/calendar" element={<CalendarView />} />
            <Route path="/calendar/:year/:month" element={<CalendarView />} />
            <Route path="/chat" element={<ChatView />} />
            <Route path="/chat/:conversationId" element={<ChatView />} />
            <Route path="/drive" element={<DriveView />} />
            <Route path="/drive/folder/*" element={<DriveView />} />
            <Route path="/notes" element={<NotesView />} />
            <Route path="/notes/:id" element={<NotesView />} />
            <Route path="/global-search" element={<GlobalSearch />} />
            <Route path="/analytics" element={<AnalyticsDashboard />} />
            <Route path="/ai-chat" element={<AIChat />} />
            <Route path="/trash" element={<TrashView />} />
            <Route path="/space" element={<SpaceManager />} />
            <Route path="/tags" element={<TagManager />} />
          </Routes>
        </div>
      </div>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppLayout />
    </BrowserRouter>
  );
}

export default App;
