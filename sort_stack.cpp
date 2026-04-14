#include <iostream>
#include <string>
#include <vector>
#include <stack>

using namespace std;

void pls_sort_my_stack(stack<int>& s , int temp){
    if(s.empty() || temp>=s.top()){
        s.push(temp);
        return;
    }

    int temp1 = s.top();
    s.pop();
    pls_sort_my_stack(s, temp);
    s.push(temp1);
}

void sort_stack(stack<int>& s){
    if (s.empty()){
        return ;
    }

    int temp = s.top();
    s.pop();
    sort_stack(s);

    pls_sort_my_stack(s, temp);

    return ;
}

// Helper to print stack from top to bottom without destroying it
void print_stack(const stack<int>& s) {
    stack<int> temp = s; // copy
    cout << "[";
    while (!temp.empty()) {
        cout << temp.top();
        temp.pop();
        if (!temp.empty()) cout << ", ";
    }
    cout << "]";
}

int main() {
    // Test case 1: empty stack
    {
        stack<int> s;
        cout << "Test 1 - empty stack: ";
        print_stack(s);
        cout << " -> ";
        sort_stack(s);
        print_stack(s);
        cout << endl;
    }

    // Test case 2: single element
    {
        stack<int> s;
        s.push(42);
        cout << "Test 2 - single element: ";
        print_stack(s);
        cout << " -> ";
        sort_stack(s);
        print_stack(s);
        cout << endl;
    }

    // Test case 3: already sorted ascending (top is smallest)
    {
        stack<int> s;
        // push 1,2,3,4,5 so top is 5? Actually we want sorted stack where smallest at top?
        // Our sort algorithm sorts in ascending order with smallest at top? Let's see.
        // We'll just push random and see output.
        s.push(5);
        s.push(1);
        s.push(4);
        s.push(2);
        s.push(3);
        cout << "Test 3 - random order: ";
        print_stack(s);
        cout << " -> ";
        sort_stack(s);
        print_stack(s);
        cout << endl;
    }

    // Test case 4: descending order (largest at top)
    {
        stack<int> s;
        s.push(5);
        s.push(4);
        s.push(3);
        s.push(2);
        s.push(1);
        cout << "Test 4 - descending (5..1): ";
        print_stack(s);
        cout << " -> ";
        sort_stack(s);
        print_stack(s);
        cout << endl;
    }

    // Test case 5: with duplicates
    {
        stack<int> s;
        s.push(2);
        s.push(5);
        s.push(2);
        s.push(3);
        s.push(5);
        s.push(1);
        cout << "Test 5 - with duplicates: ";
        print_stack(s);
        cout << " -> ";
        sort_stack(s);
        print_stack(s);
        cout << endl;
    }

    return 0;
}