// Basic test to verify Jest is working
describe('Jest Setup', () => {
  test('should run basic test', () => {
    expect(1 + 1).toBe(2);
  });

  test('should handle arrays', () => {
    const arr = [1, 2, 3];
    expect(arr).toHaveLength(3);
    expect(arr).toContain(2);
  });

  test('should handle objects', () => {
    const obj = { name: 'test', value: 42 };
    expect(obj).toHaveProperty('name');
    expect(obj.name).toBe('test');
  });

  test('should work with DOM', () => {
    document.body.innerHTML = '<div id="test">Hello World</div>';
    const element = document.getElementById('test');
    expect(element).toBeInTheDocument();
    expect(element.textContent).toBe('Hello World');
  });
});
