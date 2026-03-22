import { useEffect, useState, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Search, User, Mail, Phone, Building, ChevronRight, X, ArrowLeft } from 'lucide-react';
import { fetchContacts, searchContacts, fetchContact, fetchContactGroups } from '../utils/api';
import type { Contact } from '../types';

export default function ContactList() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [groups, setGroups] = useState<string[]>([]);
  const [selectedGroup, setSelectedGroup] = useState('');
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    fetchContactGroups().then(setGroups).catch(console.error);
  }, []);

  useEffect(() => {
    setLoading(true);
    const load = query.trim()
      ? searchContacts(query.trim(), 0, 500)
      : fetchContacts({ limit: 500, group: selectedGroup || undefined });
    load
      .then((res) => {
        setContacts(res.contacts);
        setTotal(res.total);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [query, selectedGroup]);

  useEffect(() => {
    if (id) {
      setDetailLoading(true);
      fetchContact(Number(id))
        .then(setSelectedContact)
        .catch(console.error)
        .finally(() => setDetailLoading(false));
    } else {
      setSelectedContact(null);
    }
  }, [id]);

  const grouped = useMemo(() => {
    const map: Record<string, Contact[]> = {};
    const getName = (c: Contact) => c.name || (c.emails.length > 0 ? c.emails[0].address : '');
    const sorted = [...contacts].sort((a, b) =>
      getName(a).localeCompare(getName(b))
    );
    for (const c of sorted) {
      const displayName = getName(c);
      const letter = (displayName || '#').charAt(0).toUpperCase();
      const key = /[A-Z]/.test(letter) ? letter : '#';
      if (!map[key]) map[key] = [];
      map[key].push(c);
    }
    return Object.entries(map).sort(([a], [b]) => {
      if (a === '#') return 1;
      if (b === '#') return -1;
      return a.localeCompare(b);
    });
  }, [contacts]);

  function handleViewEmails(email: string) {
    navigate(`/search?q=${encodeURIComponent(email)}`);
  }

  if (selectedContact || detailLoading) {
    return (
      <div className="contact-detail-view">
        <div className="contact-detail-toolbar">
          <button className="btn-back" onClick={() => navigate('/contacts')}>
            <ArrowLeft size={16} />
            Back to Contacts
          </button>
        </div>
        {detailLoading ? (
          <div className="contact-detail-loading">Loading contact...</div>
        ) : selectedContact ? (
          <div className="contact-detail-card">
            <div className="contact-detail-avatar">
              <User size={48} />
            </div>
            <h2 className="contact-detail-name">{selectedContact.name}</h2>
            {selectedContact.title && (
              <div className="contact-detail-title">{selectedContact.title}</div>
            )}
            {selectedContact.organization && (
              <div className="contact-detail-org">
                <Building size={14} /> {selectedContact.organization}
              </div>
            )}

            {selectedContact.emails.length > 0 && (
              <div className="contact-detail-section">
                <h3><Mail size={14} /> Email</h3>
                {selectedContact.emails.map((email, i) => (
                  <div key={i} className="contact-detail-row">
                    <span className="contact-detail-value">{email.address}</span>
                    <button
                      className="contact-email-link"
                      onClick={() => handleViewEmails(email.address)}
                    >
                      View emails
                    </button>
                  </div>
                ))}
              </div>
            )}

            {selectedContact.phones.length > 0 && (
              <div className="contact-detail-section">
                <h3><Phone size={14} /> Phone</h3>
                {selectedContact.phones.map((phone, i) => (
                  <div key={i} className="contact-detail-value">{phone.number} ({phone.type})</div>
                ))}
              </div>
            )}

            {selectedContact.groups.length > 0 && (
              <div className="contact-detail-section">
                <h3>Groups</h3>
                <div className="contact-detail-groups">
                  {selectedContact.groups.map((g, i) => (
                    <span key={i} className="contact-group-tag">{g}</span>
                  ))}
                </div>
              </div>
            )}

            {selectedContact.notes && (
              <div className="contact-detail-section">
                <h3>Notes</h3>
                <div className="contact-detail-notes">{selectedContact.notes}</div>
              </div>
            )}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="contact-list-container">
      <div className="contact-list-header">
        <h2>Contacts</h2>
        <span className="contact-list-count">{total.toLocaleString()} contacts</span>
      </div>

      <div className="contact-list-toolbar">
        <div className="contact-search-wrapper">
          <Search size={16} />
          <input
            type="text"
            placeholder="Search contacts..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="contact-search-input"
          />
          {query && (
            <button className="search-clear" onClick={() => setQuery('')}>
              <X size={14} />
            </button>
          )}
        </div>
        {groups.length > 0 && (
          <select
            className="contact-group-filter"
            value={selectedGroup}
            onChange={(e) => setSelectedGroup(e.target.value)}
          >
            <option value="">All Groups</option>
            {groups.map((g) => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>
        )}
      </div>

      <div className="contact-list-body">
        {loading ? (
          <div className="contact-list-loading">Loading contacts...</div>
        ) : contacts.length === 0 ? (
          <div className="contact-list-empty">No contacts found</div>
        ) : (
          grouped.map(([letter, letterContacts]) => (
            <div key={letter} className="contact-letter-group">
              <div className="contact-letter-header">{letter}</div>
              {letterContacts.map((contact) => (
                <button
                  key={contact.id}
                  className="contact-row"
                  onClick={() => navigate(`/contacts/${contact.id}`)}
                >
                  <div className="contact-row-avatar">
                    <User size={18} />
                  </div>
                  <div className="contact-row-info">
                    <div className="contact-row-name">{contact.name || (contact.emails.length > 0 ? contact.emails[0].address : 'Unknown')}</div>
                    {contact.emails.length > 0 && (
                      <div className="contact-row-email">{contact.emails[0].address}</div>
                    )}
                  </div>
                  {contact.organization && (
                    <div className="contact-row-org">{contact.organization}</div>
                  )}
                  <ChevronRight size={16} className="contact-row-chevron" />
                </button>
              ))}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
