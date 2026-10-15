export default function EventsTable({ rows = [] }) {
  return <table><tbody>{rows.map((row) => <tr key={row.id || row.event_id}><td>{row.event_id}</td><td>{row.status}</td></tr>)}</tbody></table>
}