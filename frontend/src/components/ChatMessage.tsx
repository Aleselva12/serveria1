import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Check, Copy } from 'lucide-react';

export default function ChatMessage({content, assistant = false}: {content:string; assistant?:boolean}) {
  const [copied,setCopied] = useState(false);
  const [copyError,setCopyError] = useState(false);
  return <div className="chat-rich-message">
    {assistant ? <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={{
      img: ({alt}) => <span className="chat-image-label">{alt || 'Immagine non inclusa'}</span>,
      a: ({children,href}) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
      table: ({children}) => <div className="chat-table-scroll"><table>{children}</table></div>,
    }}>{content}</ReactMarkdown> : <div style={{whiteSpace:'pre-wrap'}}>{content}</div>}
    {assistant && content && <button className="chat-copy" aria-label="Copia risposta" onClick={async()=>{
      try {await navigator.clipboard.writeText(content);setCopied(true);setCopyError(false);}
      catch {setCopyError(true);}
    }}>{copied ? <Check size={14}/> : <Copy size={14}/>} {copied?'Copiata':'Copia'}</button>}
    {copyError && <small role="status">Copia non disponibile: seleziona il testo.</small>}
  </div>;
}
