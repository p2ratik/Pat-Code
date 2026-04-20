#include <bits/stdc++.h>
using namespace std;

bool isPalindrome(const string& s){
    int i=0,j=s.size()-1;
    while(i<j){
        if(s[i]!=s[j]) return false;
        ++i;--j;
    }
    return true;
}

int main(){
    // Read number of strings to process
    size_t n;
    if(!(cin >> n)) return 0;
    vector<string> inputs(n);
    for(size_t i = 0; i < n; ++i){
        cin >> inputs[i];
    }
    for(const auto& str : inputs){
        cout << (isPalindrome(str) ? "Palindrome" : "Not Palindrome") << '\n';
    }
    return 0;
}
