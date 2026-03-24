import ChatContainer from './components/ChatContainer';
import { useWidgetInfo } from './hooks/useWidgetInfo';
import './index.css';

const App = () => {
  const { info, loading } = useWidgetInfo();

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="loading-spinner" />
      </div>
    );
  }

  return <ChatContainer widgetInfo={info} />;
};

export default App;
