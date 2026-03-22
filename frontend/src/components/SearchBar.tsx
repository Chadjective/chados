import { useState, useEffect, forwardRef, type FormEvent } from 'react';
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom';
import { Search, X } from 'lucide-react';

function getSearchContext(pathname: string): {
  placeholder: string;
  route: string;
} {
  if (pathname.startsWith('/contacts')) {
    return { placeholder: 'Search contacts', route: '/contacts' };
  }
  if (pathname.startsWith('/chat')) {
    return { placeholder: 'Search chat messages', route: '/chat' };
  }
  if (pathname.startsWith('/drive')) {
    return { placeholder: 'Search files', route: '/drive' };
  }
  if (pathname.startsWith('/photos')) {
    return { placeholder: 'Search photos', route: '/photos/search' };
  }
  if (
    pathname === '/' ||
    pathname.startsWith('/label') ||
    pathname.startsWith('/email') ||
    pathname.startsWith('/thread') ||
    pathname.startsWith('/search')
  ) {
    return { placeholder: 'Search mail', route: '/search' };
  }
  // For calendar, notes, or any other section, use global search
  return { placeholder: 'Search everything', route: '/global-search' };
}

const SearchBar = forwardRef<HTMLInputElement>(function SearchBar(_props, ref) {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const currentQuery = searchParams.get('q') || '';
  const [value, setValue] = useState(currentQuery);

  const ctx = getSearchContext(location.pathname);

  useEffect(() => {
    setValue(currentQuery);
  }, [currentQuery]);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (trimmed) {
      navigate(`${ctx.route}?q=${encodeURIComponent(trimmed)}`);
    } else {
      navigate('/');
    }
  }

  function handleClear() {
    setValue('');
    navigate(location.pathname);
    if (ref && typeof ref !== 'function' && ref.current) {
      ref.current.focus();
    }
  }

  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <div className="search-input-wrapper">
        <span className="search-icon">
          <Search size={18} />
        </span>
        <input
          ref={ref}
          type="text"
          className="search-input"
          placeholder={ctx.placeholder}
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        {value && (
          <button type="button" className="search-clear" onClick={handleClear}>
            <X size={16} />
          </button>
        )}
      </div>
    </form>
  );
});

export default SearchBar;
